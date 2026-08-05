"""PDF Parser: ekstraksi teks per halaman + smart chunking berbasis heading.

Alur:
1. PyMuPDF (fitz) membaca PDF, mengambil teks per halaman beserta struktur
   blok/line dan ukuran font untuk deteksi heading.
2. Halaman dipecah menjadi segmen berdasarkan heading (font lebih besar
   dari body text).
3. Segmen yang terlalu panjang dipecah dengan
   LangChain ``RecursiveCharacterTextSplitter`` (batas kalimat/paragraf,
   bukan potong paksa), dengan overlap antar chunk.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50  # ~10% dari chunk_size
HEADING_SIZE_FACTOR = 1.15  # font > 1.15x ukuran median dianggap heading
MAX_HEADING_LENGTH = 120
MIN_SEGMENT_LEN = 120  # segmen lebih pendek digabung ke segmen sebelumnya (cegah chunk serpihan)
NO_HEADING_LABEL = "Intro"


@dataclass
class PageText:
    """Teks mentah satu halaman PDF."""

    page_number: int  # 1-based
    text: str


@dataclass
class Chunk:
    """Satu potongan teks siap di-embedding, beserta metadata."""

    text: str
    metadata: dict = field(default_factory=dict)


def extract_pages(pdf_path: str | Path) -> list[PageText]:
    """Extract teks per halaman dari PDF text-based."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {pdf_path}")

    pages: list[PageText] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:  # lewati halaman kosong / hasil scan tanpa OCR
                pages.append(PageText(page_number=i + 1, text=text))
    return pages


def parse_pdf(
    pdf_path: str | Path,
    source: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Baca PDF, deteksi heading, lalu pecah menjadi chunk ber-metadata.

    Args:
        pdf_path: Lokasi file PDF.
        source: Nama sumber (default: nama file). Dipakai sebagai metadata.
        chunk_size: Ukuran maksimum chunk (karakter).
        chunk_overlap: Jumlah karakter overlap antar chunk.

    Returns:
        List of :class:`Chunk`, masing-masing berisi metadata
        ``{"source", "page", "heading", "chunk_index"}``.
    """
    pdf_path = Path(pdf_path)
    source = source or pdf_path.name

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc):
            if not page.get_text().strip():
                continue
            lines = _page_lines(page)
            segments = _merge_short_segments(_segments_from_lines(lines))
            for heading, segment in segments:
                if segment == heading:
                    continue  # chunk berisi judul saja, tanpa isi
                if len(segment) <= chunk_size:
                    parts = [segment]
                else:
                    parts = splitter.split_text(segment)
                for part in parts:
                    chunks.append(
                        Chunk(
                            text=part,
                            metadata={
                                "page": i + 1,
                                "heading": heading or NO_HEADING_LABEL,
                            },
                        )
                    )

    for idx, chunk in enumerate(chunks):
        chunk.metadata["source"] = source
        chunk.metadata["chunk_index"] = idx
    return chunks


def _page_lines(page: fitz.Page) -> list[tuple[str, bool]]:
    """Ambil baris teks halaman, tandai mana yang berpotensi heading.

    Heading = baris yang memuat span dengan ukuran font > 1.15x median
    ukuran font di halaman tersebut.
    """
    raw = page.get_text("dict")
    sizes: list[float] = []
    all_spans: list[tuple[float, str]] = []

    for block in raw.get("blocks", []):
        if block.get("type") != 0:  # hanya blok teks
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                size = float(span.get("size", 0.0) or 0.0)
                sizes.append(size)
                all_spans.append((size, text))

    if not all_spans:
        return []
    body_size = statistics.median(sizes) or 11.0
    threshold = body_size * HEADING_SIZE_FACTOR

    lines: list[tuple[str, bool]] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            parts: list[str] = []
            is_heading = False
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                parts.append(text)
                size = float(span.get("size", 0.0) or 0.0)
                if size > threshold:
                    is_heading = True
            text = "".join(parts).strip()
            if not text:
                continue
            if text.startswith("Huawei Proprietary"):
                continue  # footer template slide, tidak informatif
            if text.isdigit():
                continue  # nomor halaman
            if is_heading and len(text) > MAX_HEADING_LENGTH:
                is_heading = False  # baris panjang = body, bukan judul
            lines.append((text, is_heading))
    return lines


def _merge_short_segments(
    segments: list[tuple[str | None, str]],
    min_len: int = MIN_SEGMENT_LEN,
) -> list[tuple[str | None, str]]:
    """Gabungkan segmen terlalu pendek ke segmen sebelumnya.

    Slide deck / PDF dengan label pendek (judul slide, footer) sering
    terpecah jadi banyak segmen serpihan. Segmen pendek digabung ke
    segmen sebelumnya agar konteks tidak hilang.
    """
    merged: list[tuple[str | None, str]] = []
    for heading, text in segments:
        if merged and len(text) < min_len:
            prev_heading, prev_text = merged[-1]
            merged[-1] = (prev_heading or heading, prev_text + "\n" + text)
        else:
            merged.append((heading, text))
    return merged


def _segments_from_lines(
    lines: list[tuple[str, bool]],
) -> list[tuple[str | None, str]]:
    """Kelompokkan baris menjadi segmen yang dimulai dari tiap heading."""
    segments: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_parts: list[str] = []

    for text, is_heading in lines:
        if is_heading:
            if current_parts:
                segments.append((current_heading, "\n".join(current_parts).strip()))
            current_heading = text
            current_parts = [text]
        else:
            current_parts.append(text)

    if current_parts:
        segments.append((current_heading, "\n".join(current_parts).strip()))
    return [seg for seg in segments if seg[1]]
