"""Markdown/Plain-text Parser: split per heading ATX + smart chunking.

Alur:
1. Baca file .md/.txt, potong jadi segmen berdasarkan heading markdown
   (``#``, ``##``, dst). Teks sebelum heading pertama dianggap segmen
   "Intro". Blok kode (fence ``` / ~~~) dilewati agar ``#`` di dalam
   kode tidak dikira heading.
2. Segmen panjang dipecah dengan LangChain ``RecursiveCharacterTextSplitter``
   (parameter sama persis dengan pdf_parser) supaya chunk konsisten
   lintas format.
3. Metadata: source, page=1, heading (judul segmen, fallback "Intro"),
   chunk_index berurutan global.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.pdf_parser import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, Chunk

logger = logging.getLogger(__name__)

NO_HEADING_LABEL = "Intro"

# Heading ATX: 1-6 tanda # diikuti spasi. Group(2) = teks judul.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TRAILING_HASHES_RE = re.compile(r"\s+#+\s*$")
_FENCE_PREFIXES = ("```", "~~~")


def parse_markdown(
    path: str | Path,
    source: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Baca .md/.txt, pecah per heading markdown, lalu chunk ber-metadata.

    Args:
        path: Lokasi file .md/.txt/.markdown.
        source: Nama sumber (default: nama file). Dipakai sebagai metadata.
        chunk_size: Ukuran maksimum chunk (karakter).
        chunk_overlap: Jumlah karakter overlap antar chunk.

    Returns:
        List of :class:`Chunk` dengan metadata
        ``{"source", "page", "heading", "chunk_index"}`` (page selalu 1).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    source = source or path.name

    # utf-8-sig: tahan BOM (umum di file .txt Windows); errors="replace"
    # agar file dengan byte tidak valid tetap bisa diproses.
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for heading, segment in _segments_from_markdown(text):
        parts = [segment] if len(segment) <= chunk_size else splitter.split_text(segment)
        for part in parts:
            chunks.append(
                Chunk(
                    text=part,
                    metadata={"page": 1, "heading": heading or NO_HEADING_LABEL},
                )
            )

    for idx, chunk in enumerate(chunks):
        chunk.metadata["source"] = source
        chunk.metadata["chunk_index"] = idx
    return chunks


def _segments_from_markdown(text: str) -> list[tuple[str | None, str]]:
    """Pecah teks markdown menjadi segmen (heading, isi) per heading ATX.

    - Heading memulai segmen baru; baris heading ikut disertakan sebagai
      baris pertama isi (sama seperti pdf_parser).
    - Segmen yang hanya berisi judul (tanpa isi) di-skip.
    - Fence kode ditandai agar ``#``/``###`` di dalamnya tidak dianggap heading.
    """
    segments: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_heading_raw: str | None = None
    current_parts: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal current_heading, current_heading_raw, current_parts
        body = "\n".join(current_parts).strip()
        if body and body != current_heading_raw:
            segments.append((current_heading, body))
        current_heading = current_heading_raw = None
        current_parts = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(_FENCE_PREFIXES):
            in_fence = not in_fence
            current_parts.append(raw_line)
            continue
        match = _HEADING_RE.match(line) if not in_fence else None
        if match:
            flush()
            current_heading_raw = line
            current_heading = _clean_heading(match.group(2))
            current_parts = [raw_line]
        else:
            current_parts.append(raw_line)

    flush()
    return segments


def _clean_heading(raw: str) -> str:
    """Bersihkan judul heading: trailing # (ATX closing), emphasis, backtick."""
    heading = _TRAILING_HASHES_RE.sub("", raw)
    return heading.strip().strip("*_`").strip()
