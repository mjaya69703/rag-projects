"""Reranker cross-encoder untuk meningkatkan kualitas retrieval.

Model: ``sentence-transformers/cross-encoder/ms-marco-MiniLM-L-6-v2``
(lazy-load sekali per proses). Bila model gagal dimuat / nonaktif,
urutan hasil hybrid dipakai apa adanya (fallback aman).

Aktif via env ``RERANK_ENABLED`` (default: true); matikan dengan
``RERANK_ENABLED=0`` (dipakai test agar cepat & deterministik).
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker: object | bool | None = None
_reranker_lock = threading.Lock()


def enabled() -> bool:
    """True bila env RERANK_ENABLED tidak melarang (default: aktif)."""
    value = os.getenv("RERANK_ENABLED", "true").strip().lower()
    return value not in {"", "0", "false", "no", "off"}


def _get_reranker() -> object | bool:
    """Load model sekali; False = nonaktif permanen untuk proses ini."""
    global _reranker
    if _reranker is not None:
        return _reranker
    with _reranker_lock:
        if _reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                _reranker = CrossEncoder(RERANK_MODEL)
                logger.info("Reranker cross-encoder siap: %s", RERANK_MODEL)
            except Exception:
                logger.exception(
                    "gagal memuat reranker; nonaktif untuk proses ini"
                )
                _reranker = False
    return _reranker


def rerank(query: str, items: list) -> list:
    """Urutkan ulang item (objek berelemen ``.text``) berdasarkan relevansi.

    Skor cross-encoder menentukan urutan; item paling relevan di depan.
    Return list baru — urutan asli dipertahankan bila nonaktif/gagal.
    """
    if not enabled() or not items:
        return list(items)
    model = _get_reranker()
    if model is False:
        return list(items)
    try:
        pairs = [[query, getattr(item, "text", "")] for item in items]
        scores = model.predict(pairs)
        ranked = sorted(
            zip(items, scores, strict=False),
            key=lambda p: float(p[1]),
            reverse=True,
        )
        return [item for item, _score in ranked]
    except Exception:
        logger.exception("rerank gagal, pakai urutan semula")
        return list(items)
