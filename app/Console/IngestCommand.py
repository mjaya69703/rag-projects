"""CLI command for ingesting documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.Core.Config import Settings
from app.Repositories.DocumentRepository import DocumentRepository
from app.Repositories.VectorRepository import VectorRepository
from app.Services.IngestionService import IngestionService


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into Knowledge Base")
    parser.add_argument("path", help="Path to document file, directory, or URL")
    parser.add_argument("--category", "-c", default="Umum", help="Document category")
    opts = parser.parse_args(args)

    target = opts.path
    settings = Settings()
    vector_repo = VectorRepository(persist_dir=settings.persist_dir)
    doc_repo = DocumentRepository(db_path=settings.db_path)
    service = IngestionService(vector_repo=vector_repo, document_repo=doc_repo, settings=settings)

    if target.startswith("http://") or target.startswith("https://"):
        print(f"Mengunduh dan mengindeks URL: {target}...")
        n = service.ingest_url(target, category=opts.category)
        print(f"✅ Sukses mengindeks {n} chunks dari URL.")
    else:
        path = Path(target)
        if not path.exists():
            print(f"❌ File/folder tidak ditemukan: {path}")
            sys.exit(1)
        if path.is_file():
            print(f"Mengindeks file: {path.name}...")
            n = service.ingest_file(path, source=path.name, category=opts.category)
            print(f"✅ Sukses mengindeks {n} chunks dari {path.name}.")
        else:
            files = [f for f in path.glob("**/*") if f.is_file() and f.suffix.lower() in (".pdf", ".md", ".txt", ".docx", ".pptx", ".html")]
            print(f"Ditemukan {len(files)} file di {path}. Memulai ingestion...")
            total = 0
            for f in files:
                try:
                    n = service.ingest_file(f, source=f.name, category=opts.category)
                    total += n
                    print(f"  + {f.name}: {n} chunks")
                except Exception as exc:
                    print(f"  x {f.name}: {exc}")
            print(f"✅ Selesai: total {total} chunks tersimpan.")
