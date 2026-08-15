"""Chat HTTP Request validation schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from app.Core.Config import SLIDING_WINDOW_DEFAULT


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    source: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None
    mode: str = Field(default="sliding", pattern="^(sliding|summary)$")
    history_n: int = Field(default=SLIDING_WINDOW_DEFAULT, ge=1, le=50)


class SessionCreateRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=100)


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
