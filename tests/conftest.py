"""Fixtures global test: reset rate limiter per-test & nonaktifkan reranker.

- Rate limiter (RATE_LIMIT_QPM=30, sliding window) memakai state global
  per proses. Tanpa reset, akumulasi POST /upload & /query antar-test/file
  bisa melampaui kuota dan memicu 429 acak (suite menjadi tidak deterministik).
- Reranker cross-encoder dimatikan agar test cepat & tidak bergantung model.
"""

from __future__ import annotations

import os

os.environ.setdefault("RERANK_ENABLED", "0")

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from app import main as main_module

    main_module._RATE_LIMIT.clear()
    yield
    main_module._RATE_LIMIT.clear()
