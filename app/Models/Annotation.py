"""Annotation and Glossary domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Annotation(BaseModel):
    id: str
    source: str
    chunk_id: str
    page: int | None = None
    text: str
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class GlossaryTerm(BaseModel):
    id: int | None = None
    term: str
    definition: str
    source: str = ""
    page: int | None = None
    category: str = "Umum"
    verified: bool = False
    created_at: str | None = None
    updated_at: str | None = None
