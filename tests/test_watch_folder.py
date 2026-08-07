"""Test fitur #6: watch_folder — scan_pending, dispatch parse_any.

Jalankan: python tests/test_watch_folder.py  atau  pytest tests/test_watch_folder.py -v
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.watch_folder import (
    SUPPORTED_EXTENSIONS,
    is_supported,
    parse_any,
    scan_pending,
)


def _touch(path: Path, mtime: float) -> None:
    path.write_text("konten", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _make_upload_dir(tmp_path: Path) -> Path:
    upload = tmp_path / "uploads"
    upload.mkdir()
    base = time.time()
    # mtime dibuat beda-beda supaya urutan bisa diuji
    _touch(upload / "a.md", base + 100)
    _touch(upload / "b.pdf", base + 200)
    _touch(upload / "c.txt", base + 300)
    _touch(upload / "d.markdown", base + 400)
    _touch(upload / "foto.png", base + 500)  # tidak didukung
    _touch(upload / "dokumen.epub", base + 600)  # tidak didukung
    _touch(upload / "tanpa_ext", base + 700)  # tidak didukung
    return upload


def test_scan_pending_finds_new_files_sorted_by_mtime(tmp_path: Path) -> None:
    upload = _make_upload_dir(tmp_path)
    pending = scan_pending(upload, indexed_sources=set())
    names = [p.name for p in pending]
    assert names == ["a.md", "b.pdf", "c.txt", "d.markdown"], names


def test_scan_pending_skips_indexed_sources(tmp_path: Path) -> None:
    upload = _make_upload_dir(tmp_path)
    pending = scan_pending(upload, indexed_sources={"a.md", "c.txt"})
    names = [p.name for p in pending]
    assert names == ["b.pdf", "d.markdown"], names


def test_scan_pending_skips_unsupported_extensions(tmp_path: Path) -> None:
    upload = _make_upload_dir(tmp_path)
    pending = scan_pending(upload, indexed_sources=set())
    for p in pending:
        assert p.suffix.lower() in SUPPORTED_EXTENSIONS
    assert all(p.name not in {"foto.png", "dokumen.epub", "tanpa_ext"} for p in pending)


def test_scan_pending_includes_office_and_html(tmp_path: Path) -> None:
    upload = tmp_path / "uploads"
    upload.mkdir()
    base = time.time()
    _touch(upload / "dokumen.docx", base + 100)
    _touch(upload / "slide.pptx", base + 200)
    _touch(upload / "halaman.html", base + 300)
    _touch(upload / "halaman2.htm", base + 400)
    names = [p.name for p in scan_pending(upload, set())]
    assert names == ["dokumen.docx", "slide.pptx", "halaman.html", "halaman2.htm"]


def test_scan_pending_empty_and_missing_dir(tmp_path: Path) -> None:
    empty = tmp_path / "kosong"
    empty.mkdir()
    assert scan_pending(empty, set()) == []
    assert scan_pending(tmp_path / "tidak-ada", set()) == []


def test_scan_pending_idempotent(tmp_path: Path) -> None:
    upload = _make_upload_dir(tmp_path)
    first = scan_pending(upload, set())
    second = scan_pending(upload, set())
    assert [p.name for p in first] == [p.name for p in second]


def test_is_supported() -> None:
    assert is_supported("catatan.MD")  # case-insensitive
    assert is_supported("file.pdf")
    assert is_supported("dokumen.docx")
    assert is_supported("slide.PPTX")
    assert is_supported("halaman.html")
    assert is_supported("halaman.htm")
    assert not is_supported("file.epub")
    assert not is_supported("tanpa_ext")


def test_parse_any_dispatches_markdown(tmp_path: Path) -> None:
    md = tmp_path / "catatan.md"
    md.write_text("# Judul\n\nIsi markdown.", encoding="utf-8")
    chunks = parse_any(md)
    assert chunks
    assert chunks[0].metadata["heading"] == "Judul"
    assert chunks[0].metadata["page"] == 1
    assert chunks[0].metadata["source"] == "catatan.md"

    txt = tmp_path / "catatan.txt"
    txt.write_text("Teks polos tanpa heading.", encoding="utf-8")
    assert parse_any(txt)  # .txt juga jalan


def test_parse_any_rejects_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "dokumen.epub"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="tidak didukung"):
        parse_any(bad)
