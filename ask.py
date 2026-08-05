"""CLI tanya jawab: query + jawaban LLM dari dokumen terindeks.

Contoh pemakaian:
    python ask.py "Singkatnya VLAN itu apa?"
    python ask.py "bagaimana routing bekerja?" -k 5
    python ask.py "routing" --source materijaringan.pdf
"""

from __future__ import annotations

import argparse

from app.llm_client import LLMError
from app.rag_engine import RAGEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Tanya jawab RAG")
    parser.add_argument("question", help="Pertanyaan / kata kunci")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Jumlah konteks (default 5)")
    parser.add_argument("--source", help="Batasi ke satu dokumen terindeks")
    args = parser.parse_args()

    engine = RAGEngine(top_k=args.top_k)
    try:
        where = {"source": args.source} if args.source else None
        answer = engine.query(args.question, where=where)
        print(f"\n{answer.answer}\n")
        if answer.cached:
            print("(dijawab dari cache — tanpa call LLM)\n")
        if answer.sources:
            print("Sumber:")
            for src in answer.sources:
                print(f"  - {src.source} | hal. {src.page} | {src.heading}")
        if answer.model:
            print(f"\n(model: {answer.model})")
    except LLMError as exc:
        print(f"Error: {exc}")
        print("Cek file .env (LLM_API_KEY, LLM_API_BASE, LLM_MODEL).")
    finally:
        engine.store.close()


if __name__ == "__main__":
    main()
