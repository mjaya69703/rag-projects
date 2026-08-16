"""Semantic Cache Service."""

from __future__ import annotations

from app.Repositories.CacheRepository import CacheEntry, CacheRepository


class CacheService:
    """Service wrapping semantic caching logic."""

    def __init__(self, cache_repo: CacheRepository) -> None:
        self.cache_repo = cache_repo

    def get(self, question: str, where: dict | None = None) -> CacheEntry | None:
        return self.cache_repo.get(question=question, where=where)

    def put(
        self,
        question: str,
        answer: str,
        model: str | None = None,
        where: dict | None = None,
    ) -> None:
        self.cache_repo.put(
            question=question,
            answer=answer,
            model=model,
            where=where,
        )

    def clear(self) -> int:
        return self.cache_repo.clear()

    def stats(self) -> dict:
        return self.cache_repo.stats()
