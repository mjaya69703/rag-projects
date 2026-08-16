"""CLI command for asking questions via terminal."""

from __future__ import annotations

import argparse

from app.Core.Config import Settings
from app.Repositories.VectorRepository import VectorRepository
from app.Services.RagService import RagService


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Query Knowledge Base from Terminal")
    parser.add_argument("question", nargs="*", help="Question to ask")
    opts = parser.parse_args(args)

    settings = Settings()
    vector_repo = VectorRepository(persist_dir=settings.persist_dir)
    rag = RagService(vector_repo=vector_repo)

    question_text = " ".join(opts.question).strip()
    if not question_text:
        print("Knowledge Base Interactive Mode (ketik 'exit' untuk keluar):")
        while True:
            try:
                q = input("\n🤔 Tanya: ").strip()
                if not q or q.lower() in ("exit", "quit", "q"):
                    break
                ans = rag.query(q)
                print(f"\n💡 Jawaban:\n{ans.answer}")
                if ans.sources:
                    print("\n📚 Sumber:")
                    for s in ans.sources:
                        print(f"  • {s.source} (hal. {s.page}) - {s.heading}")
            except (KeyboardInterrupt, EOFError):
                break
    else:
        ans = rag.query(question_text)
        print(f"\n💡 Jawaban:\n{ans.answer}")
        if ans.sources:
            print("\n📚 Sumber:")
            for s in ans.sources:
                print(f"  • {s.source} (hal. {s.page}) - {s.heading}")
