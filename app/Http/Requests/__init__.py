"""HTTP Requests package."""

from app.Http.Requests.ChatRequests import QueryRequest, RenameRequest, SessionCreateRequest
from app.Http.Requests.DocumentRequests import IngestUrlRequest, SetCategoryRequest
from app.Http.Requests.LearningRequests import (
    AnswerCardRequest,
    FlashcardAnswerRequest,
    QuizGenerateRequest,
    QuizGradeRequest,
)
from app.Http.Requests.MindmapRequests import (
    CreateAnnotationRequest,
    CreateGlossaryTermRequest,
    UpdateAnnotationRequest,
    UpdateGlossaryTermRequest,
)

__all__ = [
    "QueryRequest",
    "RenameRequest",
    "SessionCreateRequest",
    "IngestUrlRequest",
    "SetCategoryRequest",
    "AnswerCardRequest",
    "QuizGenerateRequest",
    "QuizGradeRequest",
    "FlashcardAnswerRequest",
    "CreateAnnotationRequest",
    "UpdateAnnotationRequest",
    "CreateGlossaryTermRequest",
    "UpdateGlossaryTermRequest",
]
