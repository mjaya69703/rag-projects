"""Backup data pribadi Cortex: salin folder data + export JSON data belajar.

Pemakaian:
    .venv\\Scripts\\python scripts\\backup.py [--out backups]
Output: backups/<timestamp>/ berisi chat.db, chroma_db/, uploads/, dan
learning_export.json. Aman dijalankan berulang; tidak menghapus apa pun.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.Core.Config import Settings


def _copy_dir(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    shutil.copytree(src, dst, dirs_exist_ok=True)
    return sum(1 for f in dst.rglob("*") if f.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup data Cortex")
    parser.add_argument("--out", default="backups", help="folder tujuan backup")
    args = parser.parse_args()

    settings = Settings()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Data runtime (SQLite + ChromaDB)
    n_db = _copy_dir(Path(settings.db_path).parent, out_dir / "data")
    n_upload = _copy_dir(settings.upload_dir, out_dir / "uploads")

    # 2. Export data belajar (deck, kuis, glossary, mastery)
    from app import db, learning

    export = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deck": learning.list_review_cards(settings.db_path, limit=5000),
        "quiz_history": learning.quiz_history(settings.db_path, limit=5000),
        "flashcard_stats": learning.flashcard_stats(settings.db_path, limit=5000),
        "mastery": learning.mastery_stats(settings.db_path),
        "weak_spots": learning.weak_spots(settings.db_path, limit=50),
        "progress": learning.document_progress(settings.db_path),
        "glossary": db.list_glossary(settings.db_path, limit=5000),
    }
    export_path = out_dir / "learning_export.json"
    export_path.write_text(
        json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Backup selesai -> {out_dir}")
    print(f"  data files   : {n_db}")
    print(f"  upload files : {n_upload}")
    print(f"  export       : {export_path.name} ({export_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
