"""CLI query: cari chunk paling relevan di ChromaDB (belum pakai LLM).

Contoh pemakaian:
    python query.py "Apa itu VLAN?"
    python query.py "Apa itu VLAN?" -k 5
    python query.py "routing" --source materijaringan.pdf
"""

from __future__ import annotations

import argparse

from app.vector_store import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cari chunk relevan dari dokumen terindeks"
    )
    parser.add_argument("query", help="Pertanyaan / kata kunci")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Jumlah hasil (default 5)")
    parser.add_argument("--source", help="Batasi pencarian ke satu dokumen")
    args = parser.parse_args()

    store = VectorStore()
    try:
        where = {"source": args.source} if args.source else None
        results = store.search(args.query, top_k=args.top_k, where=where)
        if not results:
            print("Tidak ada hasil. Index dulu dokumen dengan: python ingest.py <file.pdf>")
            return
        for i, r in enumerate(results, 1):
            meta = r["metadata"]
            print(f"[{i}] {meta['source']} | hal. {meta['page']} | {meta['heading']} "
                  f"| dist {r['distance']:.3f}")
            print(f"    {r['text'][:280].strip()}...\n")
    finally:
        store.close()


if __name__ == "__main__":
    main()
