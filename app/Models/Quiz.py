"""Quiz domain models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[str]
    hint: Optional[str] = None


class QuizAttempt(BaseModel):
    id: str
    source: Optional[str] = None
    questions: List[Dict[str, Any]]
    created_at: str


class QuizScore(BaseModel):
    id: Optional[int] = None
    source: Optional[str] = None
    score: int
    total: int
    created_at: str
