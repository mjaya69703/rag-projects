"""CLI ingest: index satu file PDF ke ChromaDB.

Contoh pemakaian:
    python ingest.py uploads\\materi_jaringan.pdf
    python ingest.py uploads\\materi_jaringan.pdf --source "Materi Jaringan"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.pdf_parser import parse_pdf
from app.vector_store import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Index PDF ke ChromaDB")
    parser.add_argument("pdf", help="Path ke file PDF")
    parser.add_argument(
        "--source",
        help="Nama sumber (default: nama file). Sama dokumen = di-upsert.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Hapus chunk lama dengan source yang sama sebelum index ulang.",
    )
    args = parser.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        parser.error(f"File tidak ditemukan: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        parser.error("Hanya file PDF yang didukung.")

    source = args.source or pdf.name
    print(f"Membaca {pdf} ...")
    chunks = parse_pdf(pdf, source=source)
    if not chunks:
        print("Tidak ada teks yang bisa diekstrak (PDF hasil scan?).")
        return

    store = VectorStore()
    try:
        if args.replace:
            removed = store.delete_document(source)
            print(f"Hapus {removed} chunk lama dari '{source}'")
        n = store.add_documents(chunks, source=source)
        print(f"✔ {n} chunk terindeks dari '{source}'")
        print(f"  Dokumen terindeks: {store.list_documents()}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
