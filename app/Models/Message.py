"""Message domain models."""

from __future__ import annotations

from pydantic import BaseModel


class SourceItem(BaseModel):
    source: str
    page: int | None = None
    chunk_index: int | None = None
    snippet: str | None = None
    score: float | None = None
    heading: str | None = None


class Message(BaseModel):
    id: int | None = None
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    sources: list[dict] | None = None
    created_at: str
