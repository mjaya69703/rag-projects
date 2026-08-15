"""Semantic Cache repository utilizing ChromaDB collection."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.Repositories.VectorRepository import VectorRepository

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "query_cache"
SIMILARITY_THRESHOLD = 0.25
MAX_CACHE_SIZE = 1000


def _canonical_where(where: dict | None = None) -> str:
    if where is None:
        return "null"
    return json.dumps(where, sort_keys=True, ensure_ascii=False)


@dataclass
class CacheEntry:
    answer: str
    model: str | None = None
    matched_question: str = ""


class CacheRepository:
    """Repository managing semantic query cache."""

    def __init__(
        self,
        vector_repo: VectorRepository,
        threshold: float = SIMILARITY_THRESHOLD,
        max_size: int = MAX_CACHE_SIZE,
    ) -> None:
        self.vector_repo = vector_repo
        self.client = vector_repo.client
        self.collection = self.client.get_or_create_collection(
            CACHE_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self.threshold = threshold
        self.max_size = max_size

    def get(self, question: str, where: dict | None = None) -> CacheEntry | None:
        if self.collection.count() == 0:
            return None
        embedding = self.vector_repo.model.encode(
            [question], normalize_embeddings=True
        )[0]
        result = self.collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=1,
            include=["metadatas", "documents", "distances"],
        )
        distances = result.get("distances") or [[]]
        if not distances or not distances[0]:
            return None
        distance = distances[0][0]
        if distance > self.threshold:
            return None
        meta = (result["metadatas"] or [[]])[0][0]
        if meta.get("where") != _canonical_where(where):
            return None
        doc = (result["documents"] or [[]])[0][0]
        return CacheEntry(
            answer=doc,
            model=meta.get("model") or None,
            matched_question=meta.get("question", ""),
        )

    def put(
        self,
        question: str,
        answer: str,
        model: str | None = None,
        where: dict | None = None,
    ) -> None:
        self._evict_if_needed()
        embedding = self.vector_repo.model.encode(
            [question], normalize_embeddings=True
        )[0]
        entry_id = hashlib.sha256(
            f"{question}::{_canonical_where(where)}".encode()
        ).hexdigest()[:16]
        self.collection.upsert(
            ids=[entry_id],
            documents=[answer],
            embeddings=[embedding.tolist()],
            metadatas=[
                {
                    "question": question,
                    "model": model or "",
                    "where": _canonical_where(where),
                    "created_at": str(int(time.time())),
                }
            ],
        )

    def clear(self) -> int:
        count = self.collection.count()
        if count > 0:
            self.client.delete_collection(CACHE_COLLECTION)
            self.collection = self.client.get_or_create_collection(
                CACHE_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return count

    def stats(self) -> dict:
        return {
            "size": self.collection.count(),
            "max_size": self.max_size,
            "threshold": self.threshold,
        }

    def _evict_if_needed(self) -> None:
        count = self.collection.count()
        if count < self.max_size:
            return
        data = self.collection.get(include=["metadatas"])
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []
        if not ids:
            return
        indexed = []
        for i, meta in enumerate(metas):
            try:
                ts = int((meta or {}).get("created_at", 0))
            except (ValueError, TypeError):
                ts = 0
            indexed.append((ts, ids[i]))
        indexed.sort(key=lambda x: x[0])
        num_to_delete = max(1, count - self.max_size + 1)
        delete_ids = [item[1] for item in indexed[:num_to_delete]]
        self.collection.delete(ids=delete_ids)
