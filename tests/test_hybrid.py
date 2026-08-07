"""Test hybrid search (BM25 + vector) — fitur #7.

Verifikasi: istilah eksak yang lemah di embedding tetap ketemu lewat BM25,
filter where jalan, index di-invalidate saat mutasi, fallback vector-only
saat rank_bm25 tidak tersedia.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import hybrid_search as hybrid_module
from app.hybrid_search import HybridSearch
from app.pdf_parser import parse_pdf
from app.vector_store import VectorStore
from tests.make_sample_pdf import make_sample_pdf


def _make_store(tmp_path: Path) -> VectorStore:
    sample = tmp_path / "materi_jaringan.pdf"
    make_sample_pdf(sample)
    store = VectorStore(persist_dir=tmp_path / "chroma_hybrid")
    chunks = parse_pdf(sample)
    store.add_documents(chunks, source=sample.name)
    return store


def test_hybrid_finds_exact_term(tmp_path: Path) -> None:
    """Istilah eksak ('802.1Q') harus muncul di hasil hybrid."""
    store = _make_store(tmp_path)
    try:
        results = store.search("802.1Q", top_k=5)
        assert results, "hybrid search tidak mengembalikan hasil"
        text = " ".join(r["text"] for r in results)
        assert "802.1Q" in text, "istilah eksak hilang dari hasil hybrid"
        print("[OK] istilah eksak 802.1Q ditemukan via hybrid")
    finally:
        store.close()


def test_hybrid_filter_where(tmp_path: Path) -> None:
    """Filter source tetap jalan pada jalur hybrid."""
    store = _make_store(tmp_path)
    try:
        results = store.search(
            "VLAN", top_k=3, where={"source": "materi_jaringan.pdf"}
        )
        assert results
        assert all(
            r["metadata"]["source"] == "materi_jaringan.pdf" for r in results
        )
        print("[OK] filter where bekerja di hybrid search")
    finally:
        store.close()


def test_hybrid_invalidate_on_mutation(tmp_path: Path) -> None:
    """Index BM25 dibangun ulang setelah dokumen dihapus/ditambah."""
    store = _make_store(tmp_path)
    try:
        assert store.search("OSPF", top_k=3)
        store.delete_document("materi_jaringan.pdf")
        assert store.search("OSPF", top_k=3) == []
        print("[OK] index hybrid invalidated setelah delete")
    finally:
        store.close()


def test_hybrid_fallback_without_bm25(tmp_path: Path) -> None:
    """Kalau rank_bm25 tidak tersedia, search fallback ke vector-only."""
    store = _make_store(tmp_path)
    saved = hybrid_module.BM25Okapi
    hybrid_module.BM25Okapi = None
    try:
        store._hybrid.invalidate()  # paksa rebuild dengan guard aktif
        results = store.search("Apa itu VLAN?", top_k=3)
        assert results, "fallback vector-only harus tetap mengembalikan hasil"
        assert HybridSearch.__name__  # smoke, module terimport
        print("[OK] fallback vector-only saat BM25 tidak tersedia")
    finally:
        hybrid_module.BM25Okapi = saved
        store.close()


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_hybrid_finds_exact_term(tmp_path)
        test_hybrid_filter_where(tmp_path)
        test_hybrid_invalidate_on_mutation(tmp_path)
        test_hybrid_fallback_without_bm25(tmp_path)
    print("\nSemua test hybrid search PASS ✔")


if __name__ == "__main__":
    main()
