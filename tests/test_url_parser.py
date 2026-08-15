"""Test fitur #15: url_parser — SSRF guard, fetch (MockTransport), HTML, chunk.

Semua test anti-SSRF memakai resolver palsu (tanpa DNS asli): setiap host
"di-resolve" ke IP yang kita tentukan. Jalankan:
python tests/test_url_parser.py  atau  pytest tests/test_url_parser.py -v
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.url_parser as url_parser
from app.url_parser import (
    NO_HEADING_LABEL,
    AntiBotBlock,
    SSRFBlockedError,
    URLFetchError,
    check_url,
    content_type_allowed,
    extract_title,
    fetch_url_text,
    html_to_text,
    is_blocked_ip,
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

_PUBLIC_IP = "93.184.216.34"
_orig_resolver = url_parser.resolve_host


def _install_resolver(resolver) -> None:
    """Ganti resolve_host dengan fungsi palsu (tanpa DNS asli)."""
    url_parser.resolve_host = resolver


def _pub() -> None:
    _install_resolver(lambda host: [_PUBLIC_IP])


def _restore() -> None:
    url_parser.resolve_host = _orig_resolver


def _transport_for(html: str = HTML, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"], "User-Agent harus terisi"
        return httpx.Response(status, text=html)

    return httpx.MockTransport(handler)


# ----------------------------------------------------------------------
# SSRF guard (P0-01)
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # metadata service
        "0.0.0.0",
        "100.64.0.1",       # CGNAT
        "224.0.0.1",        # multicast
        "240.0.0.1",        # reserved
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:10.0.0.1",  # IPv4-mapped IPv6 dari private IPv4
    ],
)
def test_is_blocked_ip(ip: str) -> None:
    assert is_blocked_ip(ip), f"{ip} harus diblokir"


@pytest.mark.parametrize(
    "ip",
    ["93.184.216.34", "8.8.8.8", "2606:4700::1111", "1.1.1.1"],
)
def test_is_public_ip_allowed(ip: str) -> None:
    assert not is_blocked_ip(ip), f"{ip} tidak boleh diblokir"


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "::1", "fe80::1"],
)
def test_fetch_url_text_blocks_private_ip(ip: str) -> None:
    _install_resolver(lambda host: [ip])
    try:
        with pytest.raises(SSRFBlockedError, match="diblokir"):
            fetch_url_text(URL, transport=_transport_for())
    finally:
        _restore()


def test_blocks_if_any_resolved_ip_private() -> None:
    """Satu dari beberapa IP resolve private -> seluruhnya ditolak."""
    _install_resolver(lambda host: [_PUBLIC_IP, "10.0.0.5"])
    try:
        with pytest.raises(SSRFBlockedError, match="10.0.0.5"):
            fetch_url_text(URL, transport=_transport_for())
    finally:
        _restore()


def test_blocks_non_standard_port() -> None:
    _pub()
    try:
        with pytest.raises(SSRFBlockedError, match="8080"):
            fetch_url_text("http://contoh.example:8080/x", transport=_transport_for())
    finally:
        _restore()


def test_redirect_public_to_private_blocked() -> None:
    """Redirect public -> private/metadata diblokir sebelum request kedua."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})

    def smart(host: str) -> list[str]:
        return ["169.254.169.254"] if "169.254" in host else [_PUBLIC_IP]

    _install_resolver(smart)
    try:
        with pytest.raises(SSRFBlockedError, match="169.254.169.254"):
            fetch_url_text(URL, transport=httpx.MockTransport(handler))
    finally:
        _restore()


def test_redirect_loop_bounded() -> None:
    """Redirect berantai > batas -> URLFetchError, bukan hang."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": request.url.path + "/x"})

    _pub()
    try:
        with pytest.raises(URLFetchError, match="Terlalu banyak redirect"):
            fetch_url_text(URL, transport=httpx.MockTransport(handler))
    finally:
        _restore()


# ----------------------------------------------------------------------
# Batas respons & content-type (P1-07)
# ----------------------------------------------------------------------
def test_response_too_large_rejected() -> None:
    _pub()
    try:
        big = "a" * 5000
        with pytest.raises(URLFetchError, match="terlalu besar"):
            fetch_url_text(URL, transport=_transport_for(html=big), max_bytes=1024)
    finally:
        _restore()


def test_content_type_not_allowed_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"ok": true}', headers={"content-type": "application/json"})

    _pub()
    try:
        with pytest.raises(URLFetchError, match="Content-Type"):
            fetch_url_text(URL, transport=httpx.MockTransport(handler))
    finally:
        _restore()


def test_content_type_allowed_ok() -> None:
    assert content_type_allowed("text/html; charset=UTF-8")
    assert content_type_allowed("application/pdf")
    assert content_type_allowed("text/plain")
    assert not content_type_allowed("application/json")
    assert not content_type_allowed("image/png")


def test_binary_content_rejected_at_parse() -> None:
    """Content-type hilang + isi binary -> ditolak oleh magic-byte check."""
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    _pub()
    try:
        with pytest.raises(URLFetchError, match="bukan HTML"):
            parse_url(URL, transport=httpx.MockTransport(lambda r: httpx.Response(200, content=png)))
    finally:
        _restore()


# ----------------------------------------------------------------------
# Fetch & parsing normal
# ----------------------------------------------------------------------
def test_fetch_url_text_ok() -> None:
    _pub()
    try:
        text = fetch_url_text(URL, transport=_transport_for())
        assert "Belajar Python untuk Pemula" in text
        assert "<title>" in text  # mentah: masih HTML
    finally:
        _restore()


def test_fetch_url_text_http_error() -> None:
    _pub()
    try:
        with pytest.raises(URLFetchError, match="404"):
            fetch_url_text(URL, transport=_transport_for(status=404))
    finally:
        _restore()


def test_fetch_url_text_antibot_no_curl() -> None:
    """403 -> AntiBotBlock; fallback curl sudah DIHAPUS (celah SSRF)."""
    _pub()
    try:
        with pytest.raises(AntiBotBlock, match="403"):
            fetch_url_text(URL, transport=_transport_for(status=403))
        # pastikan tidak ada jejak curl di modul (fallback dihapus)
        assert not hasattr(url_parser, "_fetch_curl")
    finally:
        _restore()


def test_fetch_url_text_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("koneksi ditolak")

    _pub()
    try:
        with pytest.raises(URLFetchError, match="Gagal mengambil"):
            fetch_url_text(URL, transport=httpx.MockTransport(handler))
    finally:
        _restore()


def test_fetch_url_text_invalid_url() -> None:
    _pub()
    try:
        with pytest.raises(ValueError, match="tidak valid"):
            fetch_url_text("ftp://bukan-http.example", transport=_transport_for())
        with pytest.raises(ValueError, match="tidak valid"):
            fetch_url_text("bukan url", transport=_transport_for())
    finally:
        _restore()


def test_check_url_accepts_public() -> None:
    _pub()
    try:
        assert check_url("https://contoh.example/") == "https://contoh.example/"
    finally:
        _restore()


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
    _pub()
    try:
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
    finally:
        _restore()


def test_parse_url_source_override() -> None:
    _pub()
    try:
        chunks = parse_url(URL, source="artikel-python", transport=_transport_for())
        assert chunks
        assert all(c.metadata["source"] == "artikel-python" for c in chunks)
    finally:
        _restore()


def test_parse_url_no_title_uses_intro() -> None:
    _pub()
    try:
        html = "<html><body><p>Konten tanpa judul sama sekali.</p></body></html>"
        chunks = parse_url(URL, transport=_transport_for(html=html))
        assert chunks
        assert all(c.metadata["heading"] == NO_HEADING_LABEL for c in chunks)
    finally:
        _restore()


def test_parse_url_invalid() -> None:
    _pub()
    try:
        with pytest.raises(ValueError, match="tidak valid"):
            parse_url("mailto:user@example.com", transport=_transport_for())
    finally:
        _restore()


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

    _pub()
    try:
        chunks = parse_url(
            "https://contoh.example/file.pdf",
            source="file-pdf",
            transport=httpx.MockTransport(handler),
        )
        assert chunks, "PDF dari URL harus menghasilkan chunk"
        assert all(c.metadata["source"] == "file-pdf" for c in chunks)
        assert any("VLAN" in c.metadata["heading"] for c in chunks)
        assert all("%PDF" not in c.text for c in chunks)
    finally:
        _restore()


def main() -> None:
    # SSRF
    for ip in [
        "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1",
        "169.254.169.254", "0.0.0.0", "100.64.0.1", "224.0.0.1",
        "240.0.0.1", "::1", "fe80::1", "fc00::1", "::ffff:10.0.0.1",
    ]:
        test_is_blocked_ip(ip)
    for ip in ["93.184.216.34", "8.8.8.8", "2606:4700::1111", "1.1.1.1"]:
        test_is_public_ip_allowed(ip)
    for ip in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "::1", "fe80::1"]:
        test_fetch_url_text_blocks_private_ip(ip)
    test_blocks_if_any_resolved_ip_private()
    test_blocks_non_standard_port()
    test_redirect_public_to_private_blocked()
    test_redirect_loop_bounded()
    # Batas respons
    test_response_too_large_rejected()
    test_content_type_not_allowed_rejected()
    test_content_type_allowed_ok()
    test_binary_content_rejected_at_parse()
    # Fetch & parsing
    test_fetch_url_text_ok()
    test_fetch_url_text_http_error()
    test_fetch_url_text_antibot_no_curl()
    test_fetch_url_text_network_error()
    test_fetch_url_text_invalid_url()
    test_check_url_accepts_public()
    test_html_to_text_strips_boilerplate()
    test_extract_title_from_title_tag()
    test_extract_title_fallback_h1()
    test_extract_title_none()
    test_parse_url_chunks_and_metadata()
    test_parse_url_source_override()
    test_parse_url_no_title_uses_intro()
    test_parse_url_invalid()
    test_parse_url_pdf_detection()
    print("\nSemua test url_parser (SSRF + fetch + parse) PASS ✔")


if __name__ == "__main__":
    main()
