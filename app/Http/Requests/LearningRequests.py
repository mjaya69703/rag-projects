"""Learning HTTP Request schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AnswerCardRequest(BaseModel):
    card_id: str = Field(..., min_length=1)
    remembered: bool


class QuizGenerateRequest(BaseModel):
    source: Optional[str] = None
    n: int = Field(default=5, ge=1, le=20)


class QuizGradeRequest(BaseModel):
    attempt_id: str = Field(..., min_length=1, max_length=64)
    answers: List[int]


class FlashcardAnswerRequest(BaseModel):
    heading: str = Field(..., min_length=1, max_length=300)
    source: str = Field(..., max_length=300)
    known: bool
