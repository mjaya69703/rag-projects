"""Document domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    text: str
    metadata: dict = Field(default_factory=dict)


class Document(BaseModel):
    source: str
    job_id: str = ""
    kind: str = "file"
    file_path: str = ""
    checksum: str = ""
    size_bytes: int = 0
    category: str = "Umum"
    status: str = "queued"  # 'queued' | 'processing' | 'ready' | 'error'
    chunks: int = 0
    error: str = ""
    version: int = 1
    created_at: str
    updated_at: str


class DocumentCategory(BaseModel):
    source: str
    category: str = "Umum"
    updated_at: str


class DeletedDocument(BaseModel):
    source: str
    deleted_at: str
