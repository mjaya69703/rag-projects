"""Semantic Cache berbasis ChromaDB untuk hemat call LLM.

Menyimpan pertanyaan + jawaban di collection ``query_cache`` pada
ChromaDB yang sama. Query baru yang mirip (cosine distance di bawah
threshold) langsung dijawab dari cache tanpa memanggil LLM.

Catatan: GPTCache (spec asli) 0.1.44 tidak kompatibel dengan stack ini
— auto-install faiss gagal & memakai API ChromaDB yang sudah deprecated
di chromadb 1.5.9. Implementasi ini menggantikannya dengan backend yang
sudah ada, tetap persistent dan berperilaku semantic.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass

from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "query_cache"
# Threshold MiniLM: parafrase ringan seperti "jelaskan apa itu VLAN" ~0.03,
# pertanyaan beda makna >0.5. 0.25 menangkap parafrase, menolak pertanyaan beda.
SIMILARITY_THRESHOLD = 0.25
MAX_CACHE_SIZE = 1000


def _canonical_where(where: dict | None = None) -> str:
    """Bentuk kanonik filter untuk pembandingan metadata (None -> "null")."""
    if where is None:
        return "null"
    return json.dumps(where, sort_keys=True, ensure_ascii=False)


@dataclass
class CacheEntry:
    answer: str
    model: str | None = None
    matched_question: str = ""


class SemanticCache:
    def __init__(
        self,
        store: VectorStore,
        threshold: float = SIMILARITY_THRESHOLD,
        max_size: int = MAX_CACHE_SIZE,
    ) -> None:
        # Simpan referensi store — akses store.model (lazy) saat dipakai,
        # supaya model embedding tidak ikut ter-load di saat init.
        self._store = store
        self.client = store.client
        self.collection = self.client.get_or_create_collection(
            CACHE_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self.threshold = threshold
        self.max_size = max_size

    # ------------------------------------------------------------------
    def get(self, question: str, where: dict | None = None) -> CacheEntry | None:
        """Cari jawaban untuk pertanyaan yang identik/mirip di cache."""
        if self.collection.count() == 0:
            return None
        embedding = self._store.model.encode(
            [question], normalize_embeddings=True
        )[0]
        result = self.collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=1,
            include=["metadatas", "documents", "distances"],
        )
        distance = (result["distances"] or [[]])[0][0]
        if distance > self.threshold:
            return None
        meta = (result["metadatas"] or [[]])[0][0]
        # Entri hanya valid jika filter dokumennya sama dengan permintaan.
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
        """Simpan jawaban LLM ke cache untuk pertanyaan tertentu."""
        self._evict_if_needed()
        embedding = self._store.model.encode(
            [question], normalize_embeddings=True
        )[0]
        self.collection.upsert(
            ids=[self._cache_id(question, where)],
            documents=[answer],
            embeddings=[embedding.tolist()],
            metadatas=[
                {
                    "question": question,
                    "model": model or "",
                    "where": _canonical_where(where),
                    "created_at": int(time.time()),
                }
            ],
        )

    # ------------------------------------------------------------------
    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> int:
        ids = self.collection.get(include=[])["ids"]
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    # ------------------------------------------------------------------
    def _evict_if_needed(self) -> None:
        """Buang entri tertua jika cache melebihi batas max_size."""
        if self.collection.count() < self.max_size:
            return
        result = self.collection.get(include=["metadatas"])
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        if not ids:
            return
        oldest = min(
            range(len(ids)),
            key=lambda i: metadatas[i].get("created_at", 0),
        )
        self.collection.delete(ids=[ids[oldest]])

    @staticmethod
    def _cache_id(question: str, where: dict | None = None) -> str:
        """ID deterministik: pertanyaan + filter. Query identik = id sama."""
        key = f"{question.strip().lower()}|{where}"
        return "q_" + hashlib.md5(key.encode("utf-8")).hexdigest()
