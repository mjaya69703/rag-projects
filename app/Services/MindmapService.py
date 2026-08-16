"""Mindmap, Document Summary, Annotation, and Glossary Service."""

from __future__ import annotations

import logging

from app.Repositories.AnnotationRepository import AnnotationRepository
from app.Repositories.VectorRepository import VectorRepository
from app.Services.LlmService import LlmService
from app.Services.Parsers.PdfParser import NO_HEADING_LABEL

logger = logging.getLogger(__name__)


class MindmapService:
    """Service handling mindmap graph extraction, auto-summarization, and glossary extraction."""

    def __init__(
        self,
        annotation_repo: AnnotationRepository,
        vector_repo: VectorRepository,
        llm: LlmService | None = None,
    ) -> None:
        self.annotation_repo = annotation_repo
        self.vector_repo = vector_repo
        self.llm = llm or LlmService()

    # ------------------------------------------------------------------
    # Mindmap & Tree Hierarchy
    # ------------------------------------------------------------------
    def generate_mindmap(self, source: str | None = None) -> dict:
        """Generate structured tree/mindmap hierarchy from indexed headings."""
        chunks = self.vector_repo.get_by_source(source) if source else self.vector_repo.list_all_chunks()
        if not chunks:
            return {"name": source or "Knowledge Base", "children": []}

        root = {"name": source or "Knowledge Base", "children": []}
        heading_map: dict[str, list[str]] = {}

        for item in chunks:
            meta = item.get("metadata", {})
            src = meta.get("source", "General")
            heading = meta.get("heading", NO_HEADING_LABEL)
            text_snippet = item.get("text", "")[:120].strip()
            heading_map.setdefault(f"{src} > {heading}", []).append(text_snippet)

        for heading, _snippets in heading_map.items():
            parts = heading.split(" > ")
            current = root
            for part in parts:
                child = next((c for c in current["children"] if c["name"] == part), None)
                if not child:
                    child = {"name": part, "children": []}
                    current["children"].append(child)
                current = child

        return root

    # ------------------------------------------------------------------
    # Document Summary
    # ------------------------------------------------------------------
    def summarize_document(self, source: str, max_tokens: int = 500) -> str:
        """Generate a concise auto-summary of an entire document."""
        chunks = self.vector_repo.get_by_source(source)
        if not chunks:
            return "Dokumen tidak ditemukan atau belum terindeks."

        selected_texts = [c["text"][:600] for c in chunks[:10]]
        material = "\n\n".join(selected_texts)
        prompt = (
            f"Buat ringkasan komprehensif dan terstruktur untuk dokumen '{source}' "
            f"berdasarkan cuplikan berikut dalam bahasa Indonesia (maksimal 3 paragraf):\n\n"
            f"{material}"
        )
        try:
            response = self.llm.chat([{"role": "user", "content": prompt}], max_tokens=max_tokens)
            return response.text.strip()
        except Exception as exc:
            logger.warning("Summarize document failed: %s", exc)
            return "Gagal menghasilkan ringkasan dokumen."

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------
    def add_annotation(
        self, source: str, chunk_id: str, text: str, page: int | None = None, tags: list[str] | None = None
    ) -> dict:
        return self.annotation_repo.create_annotation(
            source=source, chunk_id=chunk_id, text=text, page=page, tags=tags
        )

    def list_annotations(self, source: str | None = None, tag: str | None = None) -> list[dict]:
        return self.annotation_repo.list_annotations(source=source, tag=tag)

    def delete_annotation(self, ann_id: str) -> bool:
        return self.annotation_repo.delete_annotation(ann_id)

    # ------------------------------------------------------------------
    # Glossary
    # ------------------------------------------------------------------
    def list_glossary(
        self, search: str = "", source: str | None = None, verified: bool | None = None, limit: int = 100
    ) -> list[dict]:
        return self.annotation_repo.list_glossary(
            search=search, source=source, verified=verified, limit=limit
        )

    def create_glossary_term(
        self, term: str, definition: str, source: str = "", page: int | None = None, category: str = "Umum", verified: bool = False
    ) -> dict:
        return self.annotation_repo.create_glossary_term(
            term=term, definition=definition, source=source, page=page, category=category, verified=verified
        )
