"""Flashcard and Spaced Repetition domain models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ReviewCard(BaseModel):
    card_id: str
    question: str
    source: Optional[str] = None
    created_at: str
    last_reviewed: Optional[str] = None
    next_due: str
    interval_days: int = 1
    lapses: int = 0
    ease_factor: float = 2.5
    repetitions: int = 0


class FlashcardStat(BaseModel):
    heading: str
    source: Optional[str] = None
    known_count: int = 0
    unknown_count: int = 0
    updated_at: str
