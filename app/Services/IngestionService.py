"""Ingestion Service: multi-format file routing, async background jobs, and atomic indexing."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, List, Optional

from app.Core.Config import Settings, config
from app.Repositories.DocumentRepository import DocumentRepository
from app.Repositories.VectorRepository import VectorRepository
from app.Services.Parsers.MarkdownParser import parse_markdown
from app.Services.Parsers.OfficeParser import parse_docx, parse_html, parse_pptx
from app.Services.Parsers.PdfParser import Chunk, parse_pdf
from app.Services.Parsers.UrlParser import parse_url

logger = logging.getLogger(__name__)


def parse_any(path: str | Path, source: str | None = None, category: str = "Umum") -> list[Chunk]:
    """Route file parsing based on extension."""
    path = Path(path)
    ext = path.suffix.lower()
    src = source or path.name

    if ext == ".pdf":
        return parse_pdf(path, source_name=src, category=category)
    elif ext in (".md", ".txt", ".markdown"):
        return parse_markdown(path, source=src)
    elif ext == ".docx":
        return parse_docx(path, source=src)
    elif ext == ".pptx":
        return parse_pptx(path, source=src)
    elif ext in (".html", ".htm"):
        return parse_html(path, source=src)
    else:
        raise ValueError(f"Format file tidak didukung: {ext}")


def calculate_checksum(path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class IngestionService:
    """Service managing document ingestion pipeline, deduplication, and watch folder."""

    def __init__(
        self,
        vector_repo: VectorRepository,
        document_repo: DocumentRepository,
        settings: Settings | None = None,
    ) -> None:
        self.vector_repo = vector_repo
        self.document_repo = document_repo
        self.settings = settings or config
        self._lock = threading.RLock()

    def ingest_file(
        self,
        file_path: Path,
        source: str,
        category: str = "Umum",
        job_id: str = "",
    ) -> int:
        """Ingest a single local file atomically into VectorStore and registry."""
        with self._lock:
            checksum = calculate_checksum(file_path)
            chunks = parse_any(file_path, source=source, category=category)
            if not chunks:
                raise ValueError("Tidak ada konten teks yang dapat diekstrak.")

            num_chunks = self.vector_repo.replace_document(chunks, source=source, category=category)
            self.document_repo.set_document_category(source, category)
            self.document_repo.unmark_document_deleted(source)
            self.document_repo.doc_upsert(
                source=source,
                job_id=job_id,
                kind="file",
                file_path=str(file_path),
                checksum=checksum,
                size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                category=category,
                status="ready",
                chunks=num_chunks,
            )
            return num_chunks

    def ingest_url(
        self,
        url: str,
        source: str | None = None,
        category: str = "Umum",
        job_id: str = "",
    ) -> int:
        """Ingest a web URL into VectorStore and registry."""
        with self._lock:
            src = source or url
            chunks = parse_url(url, source=src)
            if not chunks:
                raise ValueError("Tidak ada konten teks yang dapat diekstrak dari URL.")

            num_chunks = self.vector_repo.replace_document(chunks, source=src, category=category)
            self.document_repo.set_document_category(src, category)
            self.document_repo.unmark_document_deleted(src)
            self.document_repo.doc_upsert(
                source=src,
                job_id=job_id,
                kind="url",
                file_path=url,
                category=category,
                status="ready",
                chunks=num_chunks,
            )
            return num_chunks

    def delete_document(self, source: str, purge_file: bool = False) -> int:
        """Delete document from VectorStore and mark deleted in registry."""
        with self._lock:
            deleted_chunks = self.vector_repo.delete_document(source)
            self.document_repo.mark_document_deleted(source)
            doc = self.document_repo.doc_get(source)
            if doc and purge_file:
                fp = doc.get("file_path")
                if fp and Path(fp).exists():
                    try:
                        Path(fp).unlink(missing_ok=True)
                    except Exception as exc:
                        logger.warning("Failed to delete physical file %s: %s", fp, exc)
            self.document_repo.doc_delete(source)
            return deleted_chunks
