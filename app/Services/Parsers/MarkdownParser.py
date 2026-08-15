"""Markdown/Plain-text Parser: split per heading ATX + smart chunking."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.Services.Parsers.PdfParser import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    NO_HEADING_LABEL,
    Chunk,
)

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TRAILING_HASHES_RE = re.compile(r"\s+#+\s*$")
_FENCE_PREFIXES = ("```", "~~~")


def parse_markdown(
    path: str | Path,
    source: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    source = source or path.name

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
    heading = _TRAILING_HASHES_RE.sub("", raw)
    return heading.strip().strip("*_`").strip()
