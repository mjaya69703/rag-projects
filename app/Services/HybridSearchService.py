"""Hybrid search: lexical BM25 + semantic vector search fused with RRF."""

from __future__ import annotations

import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

RRF_K = 60
VECTOR_POOL_FACTOR = 4


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class HybridSearchService:
    """Service combining BM25 lexical search with vector similarity via RRF."""

    def __init__(self, vector_repo: Any) -> None:
        self.vector_repo = vector_repo
        self._bm25: BM25Okapi | None = None
        self._corpus: list[dict] = []
        self._version: int = -1

    def invalidate(self) -> None:
        self._version = -1
        self._bm25 = None
        self._corpus = []

    def ensure_index(self) -> bool:
        if BM25Okapi is None:
            return False
        store = self.vector_repo
        cnt = store.collection.count()
        if self._version == cnt:
            return self._bm25 is not None
        result = store.collection.get(include=["documents", "metadatas"])
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        self._corpus = [
            {"text": d, "metadata": m}
            for d, m in zip(docs, metas, strict=True)
        ]
        if self._corpus:
            self._bm25 = BM25Okapi([tokenize(c["text"]) for c in self._corpus])
        else:
            self._bm25 = None
        self._version = cnt
        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict] | None:
        if not self.ensure_index():
            return None

        tokens = tokenize(query)
        if not tokens or not self._corpus:
            return None

        store = self.vector_repo
        embedding = store.embed_query(query) if hasattr(store, "embed_query") else store._embed_query(query)
        vec_pool = max(top_k * VECTOR_POOL_FACTOR, top_k)
        cnt = store.collection.count()
        vec_result = store.collection.query(
            query_embeddings=[embedding],
            n_results=min(vec_pool, cnt or 1),
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
            meta = next(
                (c["metadata"] for c in self._corpus if (c["text"], c["metadata"].get("source", "")) == key),
                {},
            )
            score = 1.0 - float(dist)
            results.append(
                {
                    "text": key[0],
                    "metadata": meta,
                    "distance": dist,
                    "score": round(score, 4),
                }
            )
        return results
