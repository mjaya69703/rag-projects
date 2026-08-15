"""Message domain models."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    source: str
    page: Optional[int] = None
    chunk_index: Optional[int] = None
    snippet: Optional[str] = None
    score: Optional[float] = None
    heading: Optional[str] = None


class Message(BaseModel):
    id: Optional[int] = None
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    sources: Optional[List[dict]] = None
    created_at: str
