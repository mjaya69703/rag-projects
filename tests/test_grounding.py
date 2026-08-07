"""Test grounding: relevance floor, document_status, find_locations.

Fitur: menolak menjawab saat tidak ada materi cukup relevan (bukan
mengarang), membedakan dokumen "dihapus" vs "tidak ada", dan peta lokasi
topik ("Where is X covered?").
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.pdf_parser import parse_pdf
from app.rag_engine import RAGEngine
from app.vector_store import VectorStore
from tests.make_sample_pdf import make_sample_pdf


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.text = "Jawaban dari LLM mock."

    def chat(self, messages: list[dict], max_tokens: int = 1024) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(text=self.text, model="fake-model", usage=None)


def _make_engine(tmp_path: Path, min_similarity: float) -> tuple[RAGEngine, VectorStore]:
    sample = tmp_path / "materi_jaringan.pdf"
    make_sample_pdf(sample)
    store = VectorStore(persist_dir=tmp_path / "chroma_grounding")
    chunks = parse_pdf(sample)
    store.add_documents(chunks, source=sample.name)
    engine = RAGEngine(store=store, llm=FakeLLM(), min_similarity=min_similarity)
    return engine, store


def test_relevance_floor_blocks_llm(tmp_path: Path) -> None:
    """Floor sangat ketat (0.0) -> grounded=False, LLM tidak dipanggil."""
    engine, store = _make_engine(tmp_path, min_similarity=0.0)
    try:
        answer = engine.query("Apa itu VLAN?")
        assert answer.grounded is False
        assert answer.sources, "tetap tampilkan chunk terdekat sebagai bukti"
        assert "tidak akan mengarang" in answer.answer
        assert engine.llm.calls == 0, "LLM tidak boleh dipanggil saat tidak grounded"
        print("[OK] relevance floor: tanpa materi relevan, LLM diblokir")
    finally:
        store.close()


def test_relevance_floor_allows_llm(tmp_path: Path) -> None:
    """Floor longgar (2.0) -> grounded=True, LLM dipanggil normal."""
    engine, store = _make_engine(tmp_path, min_similarity=2.0)
    try:
        answer = engine.query("Apa itu VLAN?")
        assert answer.grounded is True
        assert engine.llm.calls == 1
        print("[OK] relevance floor: materi relevan -> jawaban LLM normal")
    finally:
        store.close()


def test_document_status(tmp_path: Path) -> None:
    """Bedakan dokumen aktif, dihapus, dan tidak dikenal."""
    engine, store = _make_engine(tmp_path, min_similarity=2.0)
    db_path = tmp_path / "chat.db"
    db.init_db(db_path)
    try:
        st = engine.document_status("materi_jaringan.pdf", db_path=db_path)
        assert st["exists"] is True and st["deleted"] is False
        assert "materi_jaringan.pdf" in st["available"]

        db.record_deleted_document(db_path, "materi_jaringan.pdf")
        st = engine.document_status("materi_jaringan.pdf", db_path=db_path)
        assert st["deleted"] is True

        st = engine.document_status("file_bukan_ada.pdf", db_path=db_path)
        assert st["exists"] is False and st["deleted"] is False

        db.clear_deleted_document(db_path, "materi_jaringan.pdf")
        assert db.list_deleted_documents(db_path) == []
        print("[OK] document_status membedakan aktif/dihapus/tidak ada")
    finally:
        store.close()


def test_find_locations(tmp_path: Path) -> None:
    """'Where is X covered?': hasil di-group per (source, page, heading)."""
    engine, store = _make_engine(tmp_path, min_similarity=2.0)
    try:
        locs = engine.find_locations("VLAN", top_k=10)
        assert locs, "find_locations harus mengembalikan lokasi"
        assert all(
            {"source", "page", "heading", "count"} <= set(loc) for loc in locs
        )
        assert all(loc["count"] >= 1 for loc in locs)
        print(f"[OK] find_locations: {len(locs)} lokasi untuk 'VLAN'")
    finally:
        store.close()


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_relevance_floor_blocks_llm(tmp_path)
        test_relevance_floor_allows_llm(tmp_path)
        test_document_status(tmp_path)
        test_find_locations(tmp_path)
    print("\nSemua test grounding PASS ✔")


if __name__ == "__main__":
    main()
