"""Watch Folder: scan direktori upload untuk file yang belum terindeks.

Pure functions tanpa thread/task sendiri — integrator memanggilnya dari
lifespan/loop aplikasi (mis. tiap startup: scan lalu index yang pending).

Alur:
1. ``scan_pending`` mencari file di upload_dir yang ekstensinya didukung
   dan source-nya (nama file) belum ada di indexed_sources.
2. ``parse_any`` mendispatch parsing sesuai ekstensi ke pdf/markdown/
   office (docx/pptx) / html. URL tidak termasuk watch-folder; itu domain
   url_parser.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.md_parser import parse_markdown
from app.office_parser import parse_docx, parse_html, parse_pptx
from app.pdf_parser import Chunk, parse_pdf

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".md",
    ".txt",
    ".markdown",
    ".docx",
    ".pptx",
    ".html",
    ".htm",
}
_TEXT_EXTENSIONS = {".md", ".txt", ".markdown"}


def is_supported(path: str | Path) -> bool:
    """True jika ekstensi file masuk daftar yang didukung watch-folder."""
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def parse_any(path: str | Path, source: str | None = None) -> list[Chunk]:
    """Dispatch parsing sesuai ekstensi file (pdf/markdown/office/html).

    Args:
        path: Lokasi file.
        source: Nama sumber (default: nama file).

    Raises:
        ValueError: Ekstensi tidak didukung.
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path, source=source)
    if ext in _TEXT_EXTENSIONS:
        return parse_markdown(path, source=source)
    if ext == ".docx":
        return parse_docx(path, source=source)
    if ext == ".pptx":
        return parse_pptx(path, source=source)
    if ext in {".html", ".htm"}:
        return parse_html(path, source=source)
    raise ValueError(
        f"Ekstensi tidak didukung: {ext!r} "
        f"(dukungan: {sorted(SUPPORTED_EXTENSIONS)})"
    )


def scan_pending(upload_dir: str | Path, indexed_sources: set[str]) -> list[Path]:
    """Daftar file di upload_dir yang belum terindeks, urut mtime (lama dulu).

    Idempotent dan aman dipanggil berulang: tidak memodifikasi state apa pun.
    File dianggap sudah terindeks bila ``indexed_sources`` memuat nama
    file-nya (source default = nama file, konsisten dengan /upload).

    Args:
        upload_dir: Direktori yang dipindai.
        indexed_sources: Set source (nama file) yang sudah ada di vector store.

    Returns:
        List of Path, urut waktu modifikasi menaik (file paling lama dulu).
    """
    upload_dir = Path(upload_dir)
    if not upload_dir.is_dir():
        return []

    indexed = set(indexed_sources)
    pending = [
        p
        for p in upload_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTENSIONS
        and p.name not in indexed
    ]
    pending.sort(key=lambda p: (p.stat().st_mtime, p.name))
    return pending
