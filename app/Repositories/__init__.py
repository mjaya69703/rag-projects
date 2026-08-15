"""Repositories package."""

from app.Repositories.AnnotationRepository import AnnotationRepository
from app.Repositories.BaseRepository import BaseRepository
from app.Repositories.CacheRepository import CacheEntry, CacheRepository
from app.Repositories.DocumentRepository import DocumentRepository
from app.Repositories.LearningRepository import LearningRepository
from app.Repositories.SessionRepository import SessionRepository
from app.Repositories.VectorRepository import (
    VectorRepository,
    get_embedding_model,
    slugify_name,
    unload_embedding_model,
)

__all__ = [
    "BaseRepository",
    "SessionRepository",
    "DocumentRepository",
    "LearningRepository",
    "AnnotationRepository",
    "VectorRepository",
    "CacheRepository",
    "CacheEntry",
    "get_embedding_model",
    "unload_embedding_model",
    "slugify_name",
]
