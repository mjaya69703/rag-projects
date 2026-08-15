"""Controllers package."""

from app.Http.Controllers.AnalyticsController import router as analytics_router
from app.Http.Controllers.ChatController import router as chat_router
from app.Http.Controllers.DocumentController import router as document_router
from app.Http.Controllers.LearningController import router as learning_router
from app.Http.Controllers.MindmapController import router as mindmap_router
from app.Http.Controllers.SystemController import router as system_router

__all__ = [
    "chat_router",
    "document_router",
    "learning_router",
    "mindmap_router",
    "analytics_router",
    "system_router",
]
