"""Hybrid search: BM25 (leksikal) + vector (semantik) via Reciprocal Rank Fusion.

Embedding MiniLM lemah pada istilah eksak (nama produk, kode, angka seperti
"802.1Q" atau "port trunk"). BM25 menutup celah itu: term yang cocok persis
diangkat ke atas meskipun cosine distance-nya jauh.

Desain:
- Index BM25 dibangun lazy dari seluruh chunk di collection (tanpa embedding
  model — murni teks) dan di-invalidate oleh VectorStore saat dokumen
  ditambah/dihapus.
- Query: kandidat dari vector (top_k*4) digabung dengan kandidat BM25
  (top_k*4) via RRF (Reciprocal Rank Fusion, k=60).
- Distance tiap hasil: pakai vector distance bila item ada di kandidat
  vector; item murni BM25 diberi distance 0.0 (match leksikal eksak
  dianggap relevan kuat sehingga relevance floor tidak menolaknya).
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - tergantung environment
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover
    BM25Okapi = None

RRF_K = 60
VECTOR_POOL_FACTOR = 4  # ambil kandidat vector lebih banyak untuk fusion


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class HybridSearch:
    """Gabungkan BM25 + vector search dengan RRF."""

    def __init__(self, store: Any) -> None:
        self._store = store
        self._bm25: BM25Okapi | None = None
        self._corpus: list[dict] = []  # {"text", "metadata"}
        self._version: int = -1

    # ------------------------------------------------------------------
    def invalidate(self) -> None:
        """Paksa index dibangun ulang (dipanggil store saat ada mutasi)."""
        self._version = -1
        self._bm25 = None
        self._corpus = []

    def _ensure_index(self) -> bool:
        """Bangun index BM25 sekali. False jika BM25 tidak tersedia."""
        if BM25Okapi is None:
            return False
        store = self._store
        if self._version == store.collection.count():
            return self._bm25 is not None
        result = store.collection.get(include=["documents", "metadatas"])
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        self._corpus = [
            {"text": d, "metadata": m}
            for d, m in zip(docs, metas, strict=True)
        ]
        if self._corpus:
            self._bm25 = BM25Okapi([_tokenize(c["text"]) for c in self._corpus])
        else:
            self._bm25 = None  # korpus kosong -> search fallback ke vector
        self._version = store.collection.count()
        return True

    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict] | None:
        """Cari chunk hybrid. None jika BM25 tidak tersedia (fallback vector).

        Return list dict: {"text", "metadata", "distance"} — shape sama
        dengan VectorStore.search().
        """
        if not self._ensure_index():
            return None

        store = self._store
        tokens = _tokenize(query)
        if not tokens or not self._corpus:
            return None

        # --- Kandidat vector (top_k * VECTOR_POOL_FACTOR) ---
        embedding = store._embed_query(query)
        vec_pool = max(top_k * VECTOR_POOL_FACTOR, top_k)
        vec_result = store.collection.query(
            query_embeddings=[embedding],
            n_results=min(vec_pool, store.collection.count() or 1),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        vec_docs = (vec_result.get("documents") or [[]])[0] or []
        vec_metas = (vec_result.get("metadatas") or [[]])[0] or []
        vec_dists = (vec_result.get("distances") or [[]])[0] or []
        vec_rank: dict[tuple, int] = {}
        vec_dist: dict[tuple, float] = {}
        for i, (doc, meta, dist) in enumerate(
            zip(vec_docs, vec_metas, vec_dists, strict=True)
        ):
            key = (doc, meta.get("source", ""))
            vec_rank[key] = i + 1
            vec_dist[key] = float(dist)

        # --- Kandidat BM25 (filter where di sini) ---
        scores = self._bm25.get_scores(tokens)
        bm25_hits: list[tuple[float, int]] = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue
            meta = self._corpus[idx]["metadata"]
            if where:
                if any(meta.get(k) != v for k, v in where.items()):
                    continue
            bm25_hits.append((float(score), idx))
        bm25_hits.sort(key=lambda x: x[0], reverse=True)
        bm25_pool = bm25_hits[: max(top_k * VECTOR_POOL_FACTOR, top_k)]

        # --- RRF fusion ---
        fused: dict[tuple, float] = {}
        for rank, (_, idx) in enumerate(bm25_pool):
            item = self._corpus[idx]
            key = (item["text"], item["metadata"].get("source", ""))
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        for key, rank in vec_rank.items():
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + rank)

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results: list[dict] = []
        for key, _score in ranked:
            dist = vec_dist.get(key, 0.0)
            # cari metadata asli (dari korpus BM25)
            meta = next(
                (c["metadata"] for c in self._corpus if (c["text"], c["metadata"].get("source", "")) == key),
                {},
            )
            results.append(
                {
                    "text": key[0],
                    "metadata": meta,
                    "distance": dist,
                }
            )
        return results
