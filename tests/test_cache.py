"""Test Sprint 3: semantic cache (hit, pertanyaan mirip, persistent, eviction).

Jalankan: python tests/test_cache.py  atau  pytest tests/test_cache.py -v
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pdf_parser import parse_pdf
from app.rag_engine import RAGEngine
from app.semantic_cache import SemanticCache
from app.vector_store import VectorStore
from tests.make_sample_pdf import make_sample_pdf


class FakeLLM:
    """LLM mock dengan penghitung call."""

    def __init__(self) -> None:
        self.calls = 0
        self.text = "Jawaban dari LLM mock."

    def chat(self, messages: list[dict], max_tokens: int = 1024) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(text=self.text, model="fake-model", usage=None)


def _make_store(tmp_path: Path) -> VectorStore:
    sample = tmp_path / "materi_jaringan.pdf"
    make_sample_pdf(sample)
    store = VectorStore(persist_dir=tmp_path / "chroma_test")
    chunks = parse_pdf(sample)
    store.add_documents(chunks, source=sample.name)
    return store


def test_cache_hit_no_llm_call(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    llm = FakeLLM()
    engine = RAGEngine(store=store, llm=llm)
    try:
        a1 = engine.query("Apa itu VLAN?")
        assert not a1.cached and llm.calls == 1
        a2 = engine.query("Apa itu VLAN?")
        assert a2.cached, "query ke-2 harus dari cache"
        assert llm.calls == 1, "tidak boleh ada call LLM untuk query dari cache"
        assert a2.answer == a1.answer
        assert a2.sources
        print("[OK] hit: query identik dijawab cache tanpa call LLM")
    finally:
        store.close()


def test_cache_similar_question(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    llm = FakeLLM()
    engine = RAGEngine(store=store, llm=llm)
    try:
        engine.query("Apa itu VLAN?")
        assert llm.calls == 1
        a2 = engine.query("jelaskan apa itu VLAN")  # parafrase mirip
        assert a2.cached, "pertanyaan mirip harus HIT dari cache"
        assert llm.calls == 1
        print("[OK] similar: parafrase mirip langsung dari cache")

        # guard: pertanyaan yang beda makna TIDAK boleh false-positive
        a3 = engine.query("bagaimana cara kerja routing?")
        assert not a3.cached, "pertanyaan beda makna harus MISS"
        assert llm.calls == 2
        print("[OK] anti-false-positive: pertanyaan beda tidak dianggap sama")
    finally:
        store.close()


def test_cache_persistent(tmp_path: Path) -> None:
    persist = tmp_path / "persist"
    sample = tmp_path / "materi_jaringan.pdf"
    make_sample_pdf(sample)
    store = VectorStore(persist_dir=persist)
    chunks = parse_pdf(sample)
    store.add_documents(chunks, source=sample.name)
    cache = SemanticCache(store)
    cache.put("apa itu vlan?", "jawaban tersimpan", "fake-model")
    store.close()

    store2 = VectorStore(persist_dir=persist)
    try:
        cache2 = SemanticCache(store2)
        entry = cache2.get("apa itu vlan?")
        assert entry and entry.answer == "jawaban tersimpan"
        assert entry.model == "fake-model"
        print("[OK] persistent: cache bertahan setelah client ditutup & dibuka lagi")
    finally:
        store2.close()


def test_cache_eviction(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    cache = SemanticCache(store, max_size=3)
    try:
        for i in range(6):
            cache.put(f"pertanyaan ke-{i}", f"jawaban {i}")
        assert cache.count() <= 3
        print(f"[OK] eviction: max_size=3, isi cache = {cache.count()}")
    finally:
        store.close()


def test_cache_filter_isolated(tmp_path: Path) -> None:
    """Filter dokumen (where) harus mengisolasi entri cache antar dokumen."""
    store = _make_store(tmp_path)
    llm = FakeLLM()
    engine = RAGEngine(store=store, llm=llm)
    try:
        src = {"source": "materi_jaringan.pdf"}
        a1 = engine.query("Apa itu VLAN?", where=src)
        assert not a1.cached and llm.calls == 1
        # Pertanyaan semantik-identik TANPA filter: jawaban dari konteks
        # dokumen lain TIDAK boleh dipakai. (Pakai parafrase, bukan string
        # persis — kalau embedding-nya identik, Chroma/HNSW seri di jarak 0
        # dan pemenangnya bergantung detail implementasi, bikin test flaky.)
        a2 = engine.query("jelaskan apa itu VLAN")
        assert not a2.cached, "query tanpa filter harus MISS"
        assert llm.calls == 2
        # Filter yang sama lagi: harus HIT
        a3 = engine.query("Apa itu VLAN?", where=src)
        assert a3.cached, "query dengan filter identik harus HIT"
        assert llm.calls == 2
        print("[OK] filter: entri cache terisolasi per dokumen (tidak bocor)")
    finally:
        store.close()


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_cache_hit_no_llm_call(tmp_path)
        test_cache_similar_question(tmp_path)
        test_cache_filter_isolated(tmp_path)
        test_cache_persistent(tmp_path)
        test_cache_eviction(tmp_path)
    print("\nSemua test Sprint 3 (semantic cache) PASS ✔")


if __name__ == "__main__":
    main()
