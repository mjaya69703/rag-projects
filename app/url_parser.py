"""URL Parser: fetch halaman web + ekstraksi teks HTML + chunking.

Alur:
1. ``fetch_url_text`` mengambil HTML via httpx (User-Agent wajar,
   follow redirect, timeout). Transport httpx bisa di-inject lewat
   parameter ``transport`` supaya testable tanpa internet.
2. ``html_to_text`` memakai BeautifulSoup: buang script/style/nav/footer,
   sisakan teks utama. ``extract_title`` mengambil judul dari
   ``<title>`` atau ``<h1>`` pertama.
3. ``parse_url`` memecah teks dengan ``RecursiveCharacterTextSplitter``
   (parameter sama dengan format lain) dan memberi metadata.

Batasan: parser ini untuk halaman HTML statis/ringan. Halaman yang
dirender penuh oleh JavaScript (SPA) hanya menghasilkan konten
placeholder; untuk itu perlu headless browser di luar scope fitur ini.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from urllib.parse import urlparse

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

# Status yang menandakan proteksi anti-bot — fallback ke curl (TLS
# fingerprint curl diterima banyak situs yang menolak python-httpx).
ANTI_BOT_STATUS = {403, 429}

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


def fetch_url_text(url: str, timeout: float = DEFAULT_TIMEOUT, transport=None) -> str:
    """Ambil konten URL sebagai teks. Return string.

    Alur: coba httpx dulu (header lengkap). Kalau situs membalas 403/429
    (proteksi anti-bot yang mendeteksi TLS fingerprint python-httpx),
    fallback ke ``curl`` via subprocess — fingerprint curl diterima
    banyak situs (mis. Wikipedia) yang menolak httpx.

    Args:
        url: URL http/https.
        timeout: Timeout request (detik).
        transport: httpx transport opsional (mis. ``httpx.MockTransport``
            untuk test tanpa internet).

    Raises:
        ValueError: URL tidak valid (skema/netloc salah).
        RuntimeError: Gagal terhubung atau respons non-200, dengan pesan jelas.
    """
    content = _fetch_url_content(url, timeout=timeout, transport=transport)
    return content.decode("utf-8", "replace")


class AntiBotBlock(RuntimeError):
    """Respons 403/429 — situs menolak klien httpx (TLS fingerprint)."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"Gagal mengambil {url}: HTTP {status}")
        self.status = status


def _fetch_url_content(
    url: str, timeout: float, transport=None
) -> bytes:
    """Ambil konten mentah (bytes) dari URL, dengan fallback curl."""
    url = _validate_url(url)
    try:
        return _fetch_httpx(url, timeout=timeout, transport=transport)
    except AntiBotBlock as exc:
        logger.info("Situs memblokir httpx (%s), fallback ke curl: %s", exc.status, url)
        return _fetch_curl(url, timeout=timeout)


def _fetch_httpx(
    url: str, timeout: float, transport=None
) -> bytes:
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
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gagal mengambil {url}: {exc}") from exc

    if resp.status_code in ANTI_BOT_STATUS:
        raise AntiBotBlock(resp.status_code, url)
    if resp.status_code != 200:
        raise RuntimeError(f"Gagal mengambil {url}: HTTP {resp.status_code}")
    return resp.content


def _fetch_curl(url: str, timeout: float) -> bytes:
    """Fallback fetch via curl (TLS fingerprint diterima situs anti-bot)."""
    cmd = [
        "curl", "-sS", "-L", "--max-time", str(int(timeout)),
        "-A", DEFAULT_USER_AGENT,
        "-H", "Accept: text/html,application/xhtml+xml",
        "-H", "Accept-Language: id-ID,id;q=0.9,en;q=0.8",
        url,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout + 10
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(f"Gagal mengambil {url} (curl): {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise RuntimeError(f"Gagal mengambil {url} (curl exit {proc.returncode}): {detail}")
    return proc.stdout


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


def parse_url(
    url: str,
    source: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport=None,
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

    Returns:
        List of :class:`Chunk` dengan metadata
        ``{"source", "page", "heading", "chunk_index"}``.
    """
    source = source or url
    content = _fetch_url_content(url, timeout=timeout, transport=transport)

    # PDF dari URL: parse dengan pipeline PDF biasa (heading + halaman).
    if content.lstrip().startswith(b"%PDF-"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return parse_pdf(tmp_path, source=source)
        finally:
            os.unlink(tmp_path)

    # Selain itu: HTML statis.
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


def _validate_url(url: str) -> str:
    """Pastikan URL punya skema http/https dan host. Return URL asli."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"URL tidak valid (harus http/https): {url!r}")
    return url
