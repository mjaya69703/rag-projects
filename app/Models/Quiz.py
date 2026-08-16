"""Quiz domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: list[str]
    hint: str | None = None


class QuizAttempt(BaseModel):
    id: str
    source: str | None = None
    questions: list[dict[str, Any]]
    created_at: str


class QuizScore(BaseModel):
    id: int | None = None
    source: str | None = None
    score: int
    total: int
    created_at: str
