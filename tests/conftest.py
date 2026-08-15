"""Fixtures global test: reset rate limiter per-test.

Rate limiter (RATE_LIMIT_QPM=30, sliding window) memakai state global
per proses. Tanpa reset, akumulasi POST /upload & /query antar-test/file
bisa melampaui kuota dan memicu 429 acak (suite menjadi tidak deterministik).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from app import main as main_module

    main_module._RATE_LIMIT.clear()
    yield
    main_module._RATE_LIMIT.clear()
