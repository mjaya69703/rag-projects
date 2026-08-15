"""Central API Route Registration."""

from __future__ import annotations

from fastapi import APIRouter

from app.Http.Controllers.AnalyticsController import router as analytics_router
from app.Http.Controllers.ChatController import router as chat_router
from app.Http.Controllers.DocumentController import router as document_router
from app.Http.Controllers.LearningController import router as learning_router
from app.Http.Controllers.MindmapController import router as mindmap_router
from app.Http.Controllers.SystemController import router as system_router

api_router = APIRouter()

# Include all domain controllers
api_router.include_router(system_router)
api_router.include_router(chat_router)
api_router.include_router(document_router)
api_router.include_router(learning_router)
api_router.include_router(mindmap_router)
api_router.include_router(analytics_router)
