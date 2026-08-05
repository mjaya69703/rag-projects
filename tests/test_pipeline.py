"""Test pipeline Sprint 1: parse PDF -> chunk -> embed -> simpan -> search.

Jalankan dari root proyek:
    python tests/test_pipeline.py
atau via pytest:
    pytest tests/test_pipeline.py -v
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pdf_parser import extract_pages, parse_pdf
from app.vector_store import VectorStore
from tests.make_sample_pdf import make_sample_pdf


def _make_sample(tmp_path: Path) -> Path:
    sample = tmp_path / "materi_jaringan.pdf"
    make_sample_pdf(sample)
    return sample


def _check_parse(sample: Path) -> int:
    pages = extract_pages(sample)
    assert pages, "extract_pages() tidak mengembalikan halaman"
    assert all(p.page_number >= 1 for p in pages), "nomor halaman harus 1-based"
    total_chars = sum(len(p.text) for p in pages)
    assert total_chars > 1000, f"teks terlalu pendek: {total_chars} chars"

    chunks = parse_pdf(sample)
    assert chunks, "parse_pdf() tidak menghasilkan chunk"
    print(f"[OK] {len(pages)} halaman, {total_chars} chars, {len(chunks)} chunk")

    for i, chunk in enumerate(chunks):
        meta = chunk.metadata
        assert meta["source"] == sample.name, f"source salah: {meta}"
        assert meta["chunk_index"] == i, "chunk_index harus berurutan"
        assert meta["page"] >= 1, "page harus >= 1"
        assert meta["heading"], f"heading kosong di chunk {i}"

    headings = {c.metadata["heading"] for c in chunks}
    assert "2.1 Pengertian VLAN" in headings, f"heading VLAN tidak terdeteksi: {headings}"
    print(f"[OK] heading terdeteksi: {sorted(headings)}")

    for chunk in chunks:
        assert len(chunk.text) <= 550, f"chunk terlalu panjang: {len(chunk.text)}"
    return len(chunks)


def _check_store(tmp_path: Path, sample: Path) -> None:
    persist = tmp_path / "chroma_test"
    store = VectorStore(persist_dir=persist)

    chunks = parse_pdf(sample)
    n = store.add_documents(chunks, source=sample.name)
    assert n == len(chunks), f"tersimpan {n}, padahal chunk {len(chunks)}"
    assert store.count() == len(chunks)
    print(f"[OK] {n} chunk tersimpan di ChromaDB")

    docs = store.list_documents()
    assert docs and docs[0]["source"] == sample.name
    assert docs[0]["chunks"] == len(chunks)
    print(f"[OK] list_documents: {docs}")

    results = store.search("Apa itu VLAN?", top_k=3)
    assert results, "search() tidak mengembalikan hasil"
    top = results[0]["metadata"]["source"]
    assert top == sample.name, f"sumber hasil teratas salah: {top}"
    print(f"[OK] search top-1 source={results[0]['metadata']['source']} "
          f"page={results[0]['metadata']['page']} distance={results[0]['distance']:.4f}")

    filtered = store.search("VLAN", top_k=2, where={"source": sample.name})
    assert filtered, "search dengan filter kosong"

    removed = store.delete_document(sample.name)
    assert removed == len(chunks)
    assert store.count() == 0
    print(f"[OK] {removed} chunk terhapus")
    store.close()  # lepas file lock sebelum direktori sementara dihapus


def test_parse_pdf(tmp_path: Path) -> None:
    _check_parse(_make_sample(tmp_path))


def test_vector_store(tmp_path: Path) -> None:
    _check_store(tmp_path, _make_sample(tmp_path))


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        _check_parse(_make_sample(tmp_path))
        _check_store(tmp_path, tmp_path / "materi_jaringan.pdf")
    print("\nSemua test Sprint 1 PASS ✔")


if __name__ == "__main__":
    main()
