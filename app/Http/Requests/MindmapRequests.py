"""Annotation and Glossary HTTP Request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateAnnotationRequest(BaseModel):
    source: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    page: int | None = None
    tags: list[str] = Field(default_factory=list)


class UpdateAnnotationRequest(BaseModel):
    text: str | None = None
    tags: list[str] | None = None


class CreateGlossaryTermRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=160)
    definition: str = Field(..., min_length=1, max_length=3000)
    source: str = Field(default="", max_length=300)
    page: int | None = None
    category: str = Field(default="Umum", max_length=100)
    verified: bool = False


class UpdateGlossaryTermRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=160)
    definition: str = Field(..., min_length=1, max_length=3000)
    source: str = Field(default="", max_length=300)
    page: int | None = None
    category: str = Field(default="Umum", max_length=100)
    verified: bool = False
