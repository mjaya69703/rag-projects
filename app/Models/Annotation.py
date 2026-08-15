"""Annotation and Glossary domain models."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Annotation(BaseModel):
    id: str
    source: str
    chunk_id: str
    page: Optional[int] = None
    text: str
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class GlossaryTerm(BaseModel):
    id: Optional[int] = None
    term: str
    definition: str
    source: str = ""
    page: Optional[int] = None
    category: str = "Umum"
    verified: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
