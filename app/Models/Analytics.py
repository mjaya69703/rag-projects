"""Analytics and Ingest Job domain models."""

from __future__ import annotations

from pydantic import BaseModel


class IngestJob(BaseModel):
    id: str
    source: str
    kind: str = "file"  # file | url
    status: str = "queued"  # queued | processing | ready | error
    chunks: int = 0
    error: str = ""
    created_at: str
    updated_at: str


class WeakSpot(BaseModel):
    heading: str
    source: str
    error_rate: float
    total_reviews: int
    lapse_count: int


class ProgressItem(BaseModel):
    heading: str
    source: str
    status: str  # unread | learning | mastered
    score: float
    repetitions: int
