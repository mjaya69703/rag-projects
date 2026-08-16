"""PDF Parser: text extraction and smart heading-based chunking."""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
HEADING_SIZE_FACTOR = 1.15
MAX_HEADING_LENGTH = 120
MIN_SEGMENT_LEN = 120
NO_HEADING_LABEL = "Intro"


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def extract_pages(pdf_path: str | Path) -> list[PageText]:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {pdf_path}")

    pages: list[PageText] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                pages.append(PageText(page_number=i + 1, text=text))
    return pages


def _extract_spans_with_sizes(page: fitz.Page) -> list[dict]:
    spans = []
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block.get("type") == 0:  # text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if text:
                        spans.append({
                            "text": text,
                            "size": span["size"],
                            "flags": span.get("flags", 0),
                        })
    return spans


def _split_into_heading_segments(page: fitz.Page) -> list[dict]:
    spans = _extract_spans_with_sizes(page)
    if not spans:
        return []

    sizes = [s["size"] for s in spans]
    median_size = statistics.median(sizes)
    heading_threshold = median_size * HEADING_SIZE_FACTOR

    segments: list[dict] = []
    current_heading = NO_HEADING_LABEL
    current_lines: list[str] = []

    for span in spans:
        is_heading = (
            span["size"] > heading_threshold
            and len(span["text"]) <= MAX_HEADING_LENGTH
            and not span["text"].endswith(".")
        )
        if is_heading:
            if current_lines:
                text = " ".join(current_lines).strip()
                if text:
                    segments.append({
                        "heading": current_heading,
                        "text": text,
                    })
                current_lines = []
            current_heading = span["text"]
        else:
            current_lines.append(span["text"])

    if current_lines:
        text = " ".join(current_lines).strip()
        if text:
            segments.append({
                "heading": current_heading,
                "text": text,
            })

    # Merge short segments
    merged: list[dict] = []
    for seg in segments:
        if merged and len(seg["text"]) < MIN_SEGMENT_LEN:
            merged[-1]["text"] = merged[-1]["text"] + " " + seg["text"]
        else:
            merged.append(seg)

    return merged


def parse_pdf(
    pdf_path: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    source_name: str | None = None,
    category: str = "Umum",
) -> list[Chunk]:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {pdf_path}")

    source = source_name or pdf_path.name
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
    )

    chunks: list[Chunk] = []
    chunk_index = 0

    with fitz.open(str(pdf_path)) as doc:
        for page_idx, page in enumerate(doc):
            page_number = page_idx + 1
            segments = _split_into_heading_segments(page)

            if not segments:
                page_text = page.get_text("text").strip()
                if not page_text:
                    continue
                segments = [{"heading": NO_HEADING_LABEL, "text": page_text}]

            for seg in segments:
                text = seg["text"]
                heading = seg["heading"]
                if len(text) <= chunk_size:
                    chunks.append(
                        Chunk(
                            text=text,
                            metadata={
                                "source": source,
                                "category": category,
                                "page": page_number,
                                "heading": heading,
                                "chunk_index": chunk_index,
                            },
                        )
                    )
                    chunk_index += 1
                else:
                    split_texts = splitter.split_text(text)
                    for part in split_texts:
                        if part.strip():
                            chunks.append(
                                Chunk(
                                    text=part.strip(),
                                    metadata={
                                        "source": source,
                                        "category": category,
                                        "page": page_number,
                                        "heading": heading,
                                        "chunk_index": chunk_index,
                                    },
                                )
                            )
                            chunk_index += 1

    return chunks
