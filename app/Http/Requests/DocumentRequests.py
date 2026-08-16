"""Document HTTP Request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestUrlRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2000)
    source: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)


class SetCategoryRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
