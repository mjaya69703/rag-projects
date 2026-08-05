"""Diagnosa: bandingkan kualitas retrieval e5-small vs MiniLM untuk query produk.

Jalankan: python tests/diagnose_retrieval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb
from sentence_transformers import SentenceTransformer

from app.vector_store import QUERY_PROMPT, VectorStore

QUERIES = [
    "produk apa yang ditawarin sama mereka",
    "produk dan layanan Huawei Cloud apa saja?",
    "apa saja produk huawei cloud",
    "Apa itu VLAN?",
]

PERSIST = "data/chroma_db"


def show(title: str, model: SentenceTransformer, prompt: str | None, queries: list[str]) -> None:
    print(f"\n=== {title} ===")
    client = chromadb.PersistentClient(path=PERSIST)
    col = client.get_collection("documents")
    for q in queries:
        emb = model.encode([q], normalize_embeddings=True, prompt=prompt)[0]
        res = col.query(
            query_embeddings=[emb.tolist()], n_results=5,
            include=["documents", "metadatas", "distances"],
        )
        print(f"\n  query: {q!r}")
        for dist, doc, meta in zip(
            res["distances"][0], res["documents"][0], res["metadatas"][0], strict=True
        ):
            src = meta["source"][:22]
            print(f"    {dist:.3f} | {src:22} | hal {meta['page']:>2} | {meta['heading'][:38]:38} | {doc[:42]}")
    client.clear_system_cache()


def main() -> None:
    # e5-small (data yang sekarang ada di ChromaDB = embedding e5 passage)
    store = VectorStore()
    show("e5-small + prefix query:", store.model, QUERY_PROMPT, QUERIES)
    show("e5-small TANPA prefix:", store.model, None, QUERIES)
    store.close()

    # MiniLM (data di DB adalah embedding e5, jadi ini tidak fair secara teknis,
    # tapi tetap berguna untuk melihat peringkat relatif)
    mini = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    show("MiniLM (tanpa prefix, catatan: vektor DB masih e5)", mini, None, QUERIES)


if __name__ == "__main__":
    main()
