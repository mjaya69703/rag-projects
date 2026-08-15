"""Vector Repository for ChromaDB persistence and embedding operations."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from app.Core.Config import config
from app.Models.Document import DocumentChunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_COLLECTION = "documents"
DEFAULT_TOP_K = 5

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Singleton lazy-loaded SentenceTransformer model."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def unload_embedding_model() -> None:
    """Free embedding model from RAM."""
    global _model
    _model = None
    import gc
    gc.collect()


def slugify_name(name: str) -> str:
    """Normalize filename to a safe ChromaDB document ID."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


class VectorRepository:
    """Repository handling ChromaDB collections, vector embeddings, and search."""

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.persist_dir = Path(persist_dir or config.persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._lock = threading.RLock()

    @property
    def model(self) -> SentenceTransformer:
        return get_embedding_model()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        embedding = self.model.encode([query], normalize_embeddings=True)[0]
        return embedding.tolist()

    def count(self) -> int:
        return self.collection.count()

    def prepare_chunks(
        self, chunks: list[Any], source: str, category: str = "Umum"
    ) -> tuple[list[str], list[str], list[dict]]:
        cat = category.strip() or "Umum"
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []
        for chunk in chunks:
            meta = getattr(chunk, "metadata", {}) if hasattr(chunk, "metadata") else chunk.get("metadata", {})
            text = getattr(chunk, "text", "") if hasattr(chunk, "text") else chunk.get("text", "")
            idx = meta.get("chunk_index", len(ids))
            ids.append(f"{slugify_name(meta.get('source') or source)}_chunk_{idx}")
            documents.append(text)
            metadatas.append(
                {
                    "source": meta.get("source") or source,
                    "category": meta.get("category") or cat,
                    "page": meta.get("page"),
                    "heading": meta.get("heading", ""),
                    "chunk_index": idx,
                }
            )
        return ids, documents, metadatas

    def add_documents(
        self, chunks: Iterable[Any], source: str, category: str = "Umum"
    ) -> int:
        chunk_list = list(chunks)
        if not chunk_list:
            return 0
        with self._lock:
            ids, documents, metadatas = self.prepare_chunks(chunk_list, source, category)
            embeddings = self.embed_documents(documents)
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            return len(ids)

    def replace_document(
        self, chunks: Iterable[Any], source: str, category: str = "Umum"
    ) -> int:
        chunk_list = list(chunks)
        if not chunk_list:
            return 0
        with self._lock:
            ids, documents, metadatas = self.prepare_chunks(chunk_list, source, category)
            embeddings = self.embed_documents(documents)
            old = self.collection.get(where={"source": source}, include=[])
            old_ids = old.get("ids") or []
            if old_ids:
                self.collection.delete(ids=old_ids)
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            return len(ids)

    def query(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        where: dict | None = None,
    ) -> list[dict]:
        embedding = self.embed_query(query)
        cnt = self.collection.count()
        if cnt == 0:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, cnt),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return self._format_results(result)

    def get_by_source(self, source: str) -> list[dict]:
        data = self.collection.get(
            where={"source": source},
            include=["documents", "metadatas"],
        )
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        return [
            {"text": doc, "metadata": meta}
            for doc, meta in zip(docs, metas)
        ]

    def list_all_documents(self) -> list[str]:
        data = self.collection.get(include=["metadatas"])
        metadatas = data.get("metadatas") or []
        sources = {
            m.get("source") for m in metadatas if m and m.get("source")
        }
        return sorted(sources)

    def list_all_chunks(self) -> list[dict]:
        data = self.collection.get(include=["documents", "metadatas"])
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        return [
            {"text": doc, "metadata": meta}
            for doc, meta in zip(docs, metas)
        ]

    def delete_document(self, source: str) -> int:
        with self._lock:
            existing = self.collection.get(where={"source": source}, include=[])
            ids = existing.get("ids") or []
            if ids:
                self.collection.delete(ids=ids)
            return len(ids)

    def update_category(self, source: str, new_category: str) -> int:
        with self._lock:
            existing = self.collection.get(
                where={"source": source},
                include=["metadatas"],
            )
            ids = existing.get("ids") or []
            metadatas = existing.get("metadatas") or []
            if not ids:
                return 0
            updated_metas = []
            for meta in metadatas:
                m = dict(meta) if meta else {}
                m["category"] = new_category.strip() or "Umum"
                updated_metas.append(m)
            self.collection.update(ids=ids, metadatas=updated_metas)
            return len(ids)

    def _format_results(self, result: dict) -> list[dict]:
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        items = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            score = 1.0 - float(dist)
            items.append({
                "text": doc,
                "metadata": meta or {},
                "score": round(score, 4),
            })
        return items
