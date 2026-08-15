"""Annotation and Glossary HTTP Request schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CreateAnnotationRequest(BaseModel):
    source: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    page: Optional[int] = None
    tags: List[str] = Field(default_factory=list)


class UpdateAnnotationRequest(BaseModel):
    text: Optional[str] = None
    tags: Optional[List[str]] = None


class CreateGlossaryTermRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=160)
    definition: str = Field(..., min_length=1, max_length=3000)
    source: str = Field(default="", max_length=300)
    page: Optional[int] = None
    category: str = Field(default="Umum", max_length=100)
    verified: bool = False


class UpdateGlossaryTermRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=160)
    definition: str = Field(..., min_length=1, max_length=3000)
    source: str = Field(default="", max_length=300)
    page: Optional[int] = None
    category: str = Field(default="Umum", max_length=100)
    verified: bool = False
