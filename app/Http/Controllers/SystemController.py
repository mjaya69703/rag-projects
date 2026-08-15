"""System and Privacy Controller."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Request

from app.Core.Config import Settings
from app.Repositories.SessionRepository import SessionRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System"])


@router.get("/health")
def health_endpoint() -> dict:
    return {"status": "ok"}


@router.get("/privacy/info")
def privacy_info_endpoint(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    return {
        "status": "ok",
        "provider_label": settings.llm_provider_label,
        "external_data_flow": True,
        "redaction_enabled": settings.redaction_enabled,
        "retention": {
            "chat_days": settings.retain_chat_days,
            "cache_max_days": settings.cache_max_days,
        },
        "disclosure_text": (
            f"Aplikasi ini mengirim isi dokumen yang relevan dan riwayat chat "
            f"ke {settings.llm_provider_label} untuk menghasilkan jawaban. "
            "Data tersimpan lokal (ChromaDB + SQLite) di mesin ini."
            + (
                " Redaksi PII aktif: email/nomor telepon/pola rahasia "
                "disensor sebelum dikirim ke LLM."
                if settings.redaction_enabled
                else ""
            )
            + (
                f" Chat yang tidak diakses lebih dari {settings.retain_chat_days} hari "
                "dihapus otomatis."
                if settings.retain_chat_days > 0
                else " Chat disimpan tanpa batas waktu sampai kamu menghapusnya."
            )
        ),
    }


@router.delete("/privacy/data")
def privacy_clear_all_endpoint(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    session_repo = SessionRepository(db_path=settings.db_path)
    deleted = session_repo.delete_all_user_data()
    logger.warning("privacy: semua data pribadi dihapus: %s", deleted)
    return {"status": "ok", "deleted": deleted}


@router.delete("/privacy/cache")
def privacy_clear_cache_endpoint(request: Request) -> dict:
    store = request.app.state.store
    from app.semantic_cache import SemanticCache
    n = SemanticCache(store).clear()
    return {"status": "ok", "cleared_entries": n}
