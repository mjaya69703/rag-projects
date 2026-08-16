"""Unit test reranker cross-encoder (P2-06) — tanpa model asli.

Memakai fake CrossEncoder via monkeypatch; memverifikasi:
- urutan di-rank ulang sesuai skor,
- fallback urutan semula saat nonaktif / model gagal.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.reranker as reranker


def _items() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(text="a"),
        SimpleNamespace(text="b"),
        SimpleNamespace(text="c"),
    ]


def test_rerank_reorders_by_score(monkeypatch) -> None:
    monkeypatch.setenv("RERANK_ENABLED", "1")
    monkeypatch.setattr(reranker, "_reranker", None)

    class FakeCrossEncoder:
        def __init__(self, name: str) -> None:
            self.calls = 0

        def predict(self, pairs):
            self.calls += 1
            # b paling relevan, lalu c, lalu a
            return [0.1, 0.9, 0.5]

    monkeypatch.setattr("sentence_transformers.CrossEncoder", FakeCrossEncoder)
    out = reranker.rerank("pertanyaan", _items())
    assert [i.text for i in out] == ["b", "c", "a"]
    assert reranker._reranker is not False


def test_rerank_disabled_keeps_order(monkeypatch) -> None:
    monkeypatch.setenv("RERANK_ENABLED", "0")
    items = _items()
    assert reranker.rerank("q", items) == items


def test_rerank_empty_items(monkeypatch) -> None:
    monkeypatch.setenv("RERANK_ENABLED", "1")
    monkeypatch.setattr(reranker, "_reranker", False)
    assert reranker.rerank("q", []) == []


def test_rerank_model_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("RERANK_ENABLED", "1")
    monkeypatch.setattr(reranker, "_reranker", None)

    class BrokenCrossEncoder:
        def __init__(self, name: str) -> None:
            raise RuntimeError("gagal load model")

    monkeypatch.setattr("sentence_transformers.CrossEncoder", BrokenCrossEncoder)
    items = _items()
    assert reranker.rerank("q", items) == items, "harus fallback urutan semula"
    assert reranker._reranker is False
