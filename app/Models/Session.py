"""Session domain models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Session(BaseModel):
    id: str
    title: str = "New Chat"
    created_at: str
    updated_at: str


class SessionSummary(BaseModel):
    session_id: str
    summary_text: str
    last_message_index: int
    created_at: str
