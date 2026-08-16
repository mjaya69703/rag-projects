"""Analytics and Metrics Controller."""

from __future__ import annotations

import shutil
import statistics
import time

from fastapi import APIRouter, Depends, Request

from app.Core.Config import Settings
from app.Repositories.DocumentRepository import DocumentRepository

router = APIRouter(tags=["Analytics"])


def get_doc_repo(request: Request) -> DocumentRepository:
    return DocumentRepository(db_path=request.app.state.settings.db_path)


@router.get("/metrics")
def metrics_endpoint(request: Request) -> dict:
    m = dict(getattr(request.app.state, "metrics", {}))
    latency = m.pop("latency_ms", None)
    if latency:
        vals = sorted(latency)
        m["latency_ms_p50"] = round(statistics.median(vals), 1)
        m["latency_ms_p95"] = round(vals[int(len(vals) * 0.95) - 1], 1)
    m["latency_ms_window"] = len(latency or [])
    if hasattr(request.app.state, "started_at"):
        m["uptime_sec"] = round(time.time() - request.app.state.started_at, 1)

    try:
        settings: Settings = request.app.state.settings
        usage = shutil.disk_usage(settings.persist_dir)
        m["disk"] = {
            "persist_free_mb": round(usage.free / (1024 * 1024), 1),
            "persist_total_mb": round(usage.total / (1024 * 1024), 1),
        }
    except Exception:
        pass
    return m


@router.get("/audit")
def audit_log_endpoint(
    limit: int = 50,
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    return {"status": "ok", "entries": doc_repo.get_audit_logs(limit=limit)}


@router.get("/repeated-questions")
def repeated_questions_endpoint(
    request: Request,
    days: int = 7,
    min_hits: int = 2,
) -> dict:
    from app import db
    settings: Settings = request.app.state.settings
    return {
        "status": "ok",
        "days": days,
        "min_hits": min_hits,
        "usage": db.usage_summary(settings.db_path, days=days),
        "questions": db.repeated_questions(settings.db_path, days=days, min_hits=min_hits),
    }
