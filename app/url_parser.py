"""URL Parser: fetch halaman web + ekstraksi teks HTML + chunking.

Alur:
1. ``fetch_url_text`` mengambil HTML via httpx (User-Agent wajar, timeout,
   tanpa auto-redirect — redirect dicek manual). Transport httpx bisa
   di-inject lewat parameter ``transport`` supaya testable tanpa internet.
2. ``html_to_text`` memakai BeautifulSoup: buang script/style/nav/footer,
   sisakan teks utama. ``extract_title`` mengambil judul dari
   ``<title>`` atau ``<h1>`` pertama.
3. ``parse_url`` memecah teks dengan ``RecursiveCharacterTextSplitter``
   (parameter sama dengan format lain) dan memberi metadata.

Keamanan (P0-01): sebelum koneksi, DNS di-resolve dan SEMUA IP hasil
resolve dicek — alamat loopback/private/link-local/metadata/multicast/
reserved ditolak (termasuk IPv6 dan IPv4-mapped). Setiap redirect dicek
ulang dengan policy yang sama, port dibatasi 80/443, ukuran response
dibatasi, dan content-type di-allowlist. Fallback ``curl`` yang dulu ada
DIHAPUS: curl me-resolve DNS sendiri sehingga policy anti-SSRF tidak bisa
dijamin (jendela DNS-rebinding).

Batasan: parser ini untuk halaman HTML statis/ringan. Halaman yang
dirender penuh oleh JavaScript (SPA) hanya menghasilkan konten
placeholder; untuk itu perlu headless browser di luar scope fitur ini.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import tempfile
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.pdf_parser import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    Chunk,
    parse_pdf,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # detik
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
NO_HEADING_LABEL = "Intro"

# Status yang menandakan proteksi anti-bot.
ANTI_BOT_STATUS = {403, 429}

# ----------------------------------------------------------------------
# Kebijakan keamanan fetch (P0-01: anti-SSRF, P1-07: batas respons)
# ----------------------------------------------------------------------
MAX_REDIRECTS = 5
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}  # port lain ditolak
MAX_RESPONSE_BYTES = int(os.getenv("URL_FETCH_MAX_BYTES", str(20 * 1024 * 1024)))
ALLOWED_CONTENT_TYPES = {
    "text/html",
    "text/plain",
    "text/markdown",
    "application/xhtml+xml",
    "application/pdf",
    "application/octet-stream",  # dibiarkan; magic-byte dicek di parse_url
}

# Tag non-konten yang dibuang sebelum ekstraksi teks.
TAG_BLACKLIST = {
    "script",
    "style",
    "nav",
    "footer",
    "noscript",
    "svg",
    "template",
    "iframe",
}

# Tag blok yang diberi newline setelahnya agar paragraf tidak dempet.
BLOCK_TAGS = {
    "p",
    "div",
    "li",
    "tr",
    "blockquote",
    "pre",
    "section",
    "article",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}

_EXTRA_BLANK_RE = re.compile(r"\n{3,}")

# Network yang tidak boleh diakses (RFC 1918, loopback, link-local,
# metadata, multicast, reserved, CGNAT, doc/testing, IPv6 analog).
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),     # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("169.254.0.0/16"),    # link-local + metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),       # multicast
    ipaddress.ip_network("240.0.0.0/4"),       # reserved
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
    ipaddress.ip_network("ff00::/8"),          # IPv6 multicast
    ipaddress.ip_network("2001:db8::/32"),     # doc/testing
    ipaddress.ip_network("2001:10::/28"),      # ORCHID
]


class SSRFBlockedError(ValueError):
    """Target URL/IP diblokir policy anti-SSRF (P0-01)."""


class URLFetchError(RuntimeError):
    """Gagal mengambil URL: koneksi, redirect, ukuran, content-type, dll."""


class AntiBotBlock(URLFetchError):
    """Respons 403/429 — situs menolak klien (tidak ada fallback curl lagi)."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"Gagal mengambil {url}: HTTP {status} (diblokir situs)")
        self.status = status


def _normalize_ip(ip: str) -> ipaddress._BaseAddress:
    """IPv4-mapped IPv6 (::ffff:1.2.3.4) diperiksa sebagai IPv4."""
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return addr.ipv4_mapped
    return addr


def is_blocked_ip(ip: str) -> bool:
    """True jika IP termasuk network yang diblokir (private/loopback/dll)."""
    try:
        addr = _normalize_ip(ip)
    except ValueError:
        return True  # bukan IP valid -> tolak aman
    return any(addr in net for net in _BLOCKED_NETWORKS)


def resolve_host(host: str) -> list[str]:
    """Resolve hostname ke daftar IP unik (dipakai anti-SSRF check)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise URLFetchError(f"Gagal resolve host {host!r}: {exc}") from exc
    ips: list[str] = []
    seen: set[str] = set()
    for info in infos:
        ip = info[4][0]
        if ip not in seen:
            seen.add(ip)
            ips.append(ip)
    return ips


def check_url(url: str) -> str:
    """Validasi URL: skema http/https, port 80/443, DNS aman (anti-SSRF).

    Semua IP hasil resolve dicek; ada satu saja yang private/loopback/
    link-local/metadata/reserved -> SSRFBlockedError. Return URL asli.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
        raise ValueError(f"URL tidak valid (harus http/https): {url!r}")
    try:
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise ValueError(f"Port pada URL tidak valid: {url!r}") from None
    if port not in ALLOWED_PORTS:
        raise SSRFBlockedError(f"Port {port} tidak diizinkan (hanya 80/443): {url!r}")
    for ip in resolve_host(host):
        if is_blocked_ip(ip):
            raise SSRFBlockedError(f"Target diblokir (IP {ip} bukan publik): {url!r}")
    return url


def content_type_allowed(content_type: str | None) -> bool:
    """True jika media type masuk allowlist (header Content-Type)."""
    if not content_type:
        return True  # tanpa header -> dicek via magic bytes di parse_url
    media = content_type.split(";")[0].strip().lower()
    return media in ALLOWED_CONTENT_TYPES


def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    """Baca body streaming dengan batas ukuran (P1-07)."""
    cl = response.headers.get("content-length", "")
    if cl.isdigit() and int(cl) > max_bytes:
        raise URLFetchError(
            f"Respons terlalu besar (> {max_bytes // (1024 * 1024)} MB)"
        )
    total = 0
    parts: list[bytes] = []
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise URLFetchError(
                f"Respons terlalu besar (> {max_bytes // (1024 * 1024)} MB)"
            )
        parts.append(chunk)
    return b"".join(parts)


def _fetch_httpx(
    url: str,
    timeout: float,
    transport=None,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> bytes:
    """Fetch dengan redirect manual (tiap hop di-check anti-SSRF)."""
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    try:
        with httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=False,  # redirect dicek manual (anti-SSRF)
            headers=headers,
        ) as client:
            current = check_url(url)
            response: httpx.Response | None = None
            for _ in range(MAX_REDIRECTS + 1):
                response = client.get(current)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location", "")
                    response.close()
                    if not location:
                        raise URLFetchError(f"Redirect tanpa Location: {current}")
                    current = check_url(urljoin(current, location))
                    continue
                break
            else:
                raise URLFetchError(
                    f"Terlalu banyak redirect (maks {MAX_REDIRECTS}): {url}"
                )
            if response.status_code in ANTI_BOT_STATUS:
                raise AntiBotBlock(response.status_code, current)
            if response.status_code != 200:
                raise URLFetchError(
                    f"Gagal mengambil {current}: HTTP {response.status_code}"
                )
            if not content_type_allowed(response.headers.get("content-type", "")):
                ct = response.headers.get("content-type", "")
                raise URLFetchError(f"Content-Type tidak didukung: {ct or '(kosong)'}")
            return _read_limited(response, max_bytes)
    except httpx.HTTPError as exc:
        raise URLFetchError(f"Gagal mengambil {url}: {exc}") from exc


def _fetch_url_content(
    url: str, timeout: float, transport=None, max_bytes: int = MAX_RESPONSE_BYTES
) -> bytes:
    """Ambil konten mentah (bytes) dari URL, dengan kebijakan keamanan."""
    return _fetch_httpx(url, timeout=timeout, transport=transport, max_bytes=max_bytes)


def fetch_url_text(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    transport=None,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> str:
    """Ambil konten URL sebagai teks (UTF-8 lossy). Return string.

    Args:
        url: URL http/https.
        timeout: Timeout request (detik).
        transport: httpx transport opsional (mis. ``httpx.MockTransport``
            untuk test tanpa internet).
        max_bytes: Batas ukuran respons (byte).

    Raises:
        ValueError: URL tidak valid / target diblokir (SSRF).
        URLFetchError: Gagal terhubung, redirect berlebihan, ukuran
            melebihi batas, content-type tidak didukung, atau HTTP non-200.
    """
    content = _fetch_url_content(url, timeout=timeout, transport=transport, max_bytes=max_bytes)
    return content.decode("utf-8", "replace")


def html_to_text(html: str) -> str:
    """Ekstrak teks utama dari HTML: buang boilerplate, rapikan blank lines."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(TAG_BLACKLIST):
        tag.decompose()
    for tag in soup(BLOCK_TAGS):
        tag.append("\n")
    text = soup.get_text("")
    return _EXTRA_BLANK_RE.sub("\n\n", text).strip()


def extract_title(html: str) -> str | None:
    """Ambil judul halaman: <title>, fallback <h1> pertama. None jika kosong."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title
    if title:
        text = title.get_text(strip=True)
        if text:
            return text
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _looks_like_html_or_text(content: bytes) -> bool:
    """Magic-byte check: HTML/teks (bukan binary seperti gambar/zip)."""
    head = content[:4096]
    if b"\x00" in head:
        return False  # binary
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def parse_url(
    url: str,
    source: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport=None,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> list[Chunk]:
    """Fetch URL lalu indeks kontennya (HTML **atau PDF**).

    Deteksi otomatis via magic bytes: ``%PDF-`` → disimpan ke file temp dan
    diproses dengan :func:`parse_pdf` (heading per halaman); selain itu
    diperlakukan sebagai HTML (ekstraksi teks + chunking).

    Args:
        url: URL halaman web atau file PDF.
        source: Nama sumber (default: URL itu sendiri).
        timeout: Timeout fetch (detik).
        transport: httpx transport opsional (untuk test tanpa internet).
        max_bytes: Batas ukuran respons (byte).

    Returns:
        List of :class:`Chunk` dengan metadata
        ``{"source", "page", "heading", "chunk_index"}``.

    Raises:
        ValueError: URL tidak valid / target diblokir anti-SSRF.
        URLFetchError: Gagal fetch / konten bukan HTML/PDF yang dikenali.
    """
    source = source or url
    content = _fetch_url_content(url, timeout=timeout, transport=transport, max_bytes=max_bytes)

    # PDF dari URL: parse dengan pipeline PDF biasa (heading + halaman).
    if content.lstrip().startswith(b"%PDF-"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return parse_pdf(tmp_path, source=source)
        finally:
            os.unlink(tmp_path)

    # Selain itu harus HTML/teks yang dikenali (bukan binary misterius).
    if not _looks_like_html_or_text(content):
        raise URLFetchError("Konten bukan HTML/teks/PDF yang dikenali.")

    html = content.decode("utf-8", "replace")
    heading = extract_title(html) or NO_HEADING_LABEL
    text = html_to_text(html)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    parts = splitter.split_text(text)

    chunks: list[Chunk] = []
    for part in parts:
        if not part.strip():
            continue
        chunks.append(
            Chunk(text=part, metadata={"page": 1, "heading": heading})
        )

    for idx, chunk in enumerate(chunks):
        chunk.metadata["source"] = source
        chunk.metadata["chunk_index"] = idx
    return chunks
