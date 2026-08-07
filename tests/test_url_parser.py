"""Test fitur #15: url_parser — fetch (MockTransport), ekstraksi HTML, chunk.

Jalankan: python tests/test_url_parser.py  atau  pytest tests/test_url_parser.py -v
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.url_parser import (
    NO_HEADING_LABEL,
    extract_title,
    fetch_url_text,
    html_to_text,
    parse_url,
)

URL = "https://contoh.example/artikel"

HTML = """<!DOCTYPE html>
<html lang="id">
<head><title>Belajar Python untuk Pemula</title></head>
<body>
<nav><a href="/">Beranda</a><a href="/tentang">Tentang</a></nav>
<script>var rahasia = "jangan tampil";</script>
<style>.kode-css { color: red; }</style>
<header>Header situs</header>
<h1>Belajar Python untuk Pemula</h1>
<p>Python adalah bahasa pemrograman yang mudah dipelajari dan sangat
populer untuk otomasi, analisis data, dan pengembangan web.</p>
<p>Python memiliki sintaks yang bersih sehingga cocok untuk pemula yang
baru mengenal dunia pemrograman. Dengan ekosistem library yang luas,
hampir semua kebutuhan dapat dipenuhi tanpa menulis dari nol.</p>
<footer>Copyright 2026 Contoh Situs</footer>
</body>
</html>
"""


def _transport_for(html: str = HTML, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"], "User-Agent harus terisi"
        return httpx.Response(status, text=html)

    return httpx.MockTransport(handler)


def test_fetch_url_text_ok() -> None:
    text = fetch_url_text(URL, transport=_transport_for())
    assert "Belajar Python untuk Pemula" in text
    assert "<title>" in text  # mentah: masih HTML


def test_fetch_url_text_http_error() -> None:
    with pytest.raises(RuntimeError, match="404"):
        fetch_url_text(URL, transport=_transport_for(status=404))


def test_fetch_url_text_antibot_falls_back_to_curl() -> None:
    """403 (anti-bot) -> fallback curl; domain dummy tidak ada -> error curl."""
    with pytest.raises(RuntimeError, match="curl"):
        fetch_url_text(URL, transport=_transport_for(status=403))


def test_fetch_url_text_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("koneksi ditolak")

    with pytest.raises(RuntimeError, match="Gagal mengambil"):
        fetch_url_text(URL, transport=httpx.MockTransport(handler))


def test_fetch_url_text_invalid_url() -> None:
    with pytest.raises(ValueError, match="tidak valid"):
        fetch_url_text("ftp://bukan-http.example")
    with pytest.raises(ValueError, match="tidak valid"):
        fetch_url_text("bukan url")


def test_html_to_text_strips_boilerplate() -> None:
    text = html_to_text(HTML)
    assert "Python adalah bahasa pemrograman" in text
    assert "rahasia" not in text  # isi <script> dibuang
    assert "kode-css" not in text  # isi <style> dibuang
    assert "Beranda" not in text  # isi <nav> dibuang
    assert "Copyright 2026" not in text  # isi <footer> dibuang


def test_extract_title_from_title_tag() -> None:
    assert extract_title(HTML) == "Belajar Python untuk Pemula"


def test_extract_title_fallback_h1() -> None:
    html = "<html><body><h1>Judul dari H1</h1><p>Isi</p></body></html>"
    assert extract_title(html) == "Judul dari H1"


def test_extract_title_none() -> None:
    assert extract_title("<html><body><p>tanpa judul</p></body></html>") is None


def test_parse_url_chunks_and_metadata() -> None:
    chunks = parse_url(URL, transport=_transport_for())
    assert chunks, "parse_url() tidak menghasilkan chunk"
    for i, chunk in enumerate(chunks):
        meta = chunk.metadata
        assert meta["source"] == URL, f"source salah: {meta}"
        assert meta["chunk_index"] == i, "chunk_index harus berurutan"
        assert meta["page"] == 1, "page harus 1 untuk URL"
        assert meta["heading"] == "Belajar Python untuk Pemula"
        assert len(chunk.text) <= 550, f"chunk terlalu panjang: {len(chunk.text)}"
    joined = " ".join(c.text for c in chunks)
    assert "Python adalah bahasa pemrograman" in joined


def test_parse_url_source_override() -> None:
    chunks = parse_url(URL, source="artikel-python", transport=_transport_for())
    assert chunks
    assert all(c.metadata["source"] == "artikel-python" for c in chunks)


def test_parse_url_no_title_uses_intro() -> None:
    html = "<html><body><p>Konten tanpa judul sama sekali.</p></body></html>"
    chunks = parse_url(URL, transport=_transport_for(html=html))
    assert chunks
    assert all(c.metadata["heading"] == NO_HEADING_LABEL for c in chunks)


def test_parse_url_invalid() -> None:
    with pytest.raises(ValueError, match="tidak valid"):
        parse_url("mailto:user@example.com", transport=_transport_for())


def test_parse_url_pdf_detection() -> None:
    """URL yang berisi PDF (magic %PDF-) di-parse via pipeline PDF, bukan HTML."""
    from tests.make_sample_pdf import make_sample_pdf

    pdf_bytes = None
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "sample.pdf"
        make_sample_pdf(path)
        pdf_bytes = path.read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pdf_bytes)

    chunks = parse_url(
        "https://contoh.example/file.pdf",
        source="file-pdf",
        transport=httpx.MockTransport(handler),
    )
    assert chunks, "PDF dari URL harus menghasilkan chunk"
    # bukan chunk binary: harus ada heading yang jelas dari parse_pdf
    assert all(c.metadata["source"] == "file-pdf" for c in chunks)
    assert any("VLAN" in c.metadata["heading"] for c in chunks)
    assert all("%PDF" not in c.text for c in chunks)
