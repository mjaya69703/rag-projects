"""CLI bulk ingest: index SEMUA dokumen dalam satu folder sekaligus.

Contoh pemakaian:
    python bulk_ingest.py folder-materi
    python bulk_ingest.py folder-materi --recursive
    python bulk_ingest.py folder-materi --replace        rem index ulang walau sudah ada
    python bulk_ingest.py folder-materi --dry-run        rem lihat daftar dulu tanpa index

Perilaku:
- Mendukung PDF/MD/TXT/Markdown (sama dengan upload UI & watch-folder).
- Source = nama file (konsisten dengan watch-folder & /upload).
- File yang sudah terindeks di-SKIP (idempotent) kecuali --replace.
- Error satu file tidak menghentikan batch — dicatat dan dilanjutkan.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.vector_store import VectorStore
from app.watch_folder import SUPPORTED_EXTENSIONS, parse_any


def bulk_index(
    folder: str | Path,
    recursive: bool = False,
    replace: bool = False,
    dry_run: bool = False,
) -> dict:
    """Index semua dokumen dalam folder. Return ringkasan statistik.

    Statistik: {"found", "skipped", "indexed", "failed", "chunks"}
    """
    folder = Path(folder)
    pattern = "**/*" if recursive else "*"
    files = sorted(
        p
        for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    store = VectorStore()
    try:
        indexed = {d["source"] for d in store.list_documents()}
        todo = [f for f in files if replace or f.name not in indexed]
        skipped = len(files) - len(todo)

        if dry_run:
            return {"found": len(files), "skipped": skipped, "indexed": 0, "failed": 0, "chunks": 0}

        ok = failed = total_chunks = 0
        for path in todo:
            source = path.name
            try:
                chunks = parse_any(path, source=source)
                if not chunks:
                    print(f"  ⚠ {path.name}: tidak ada teks yang bisa diekstrak (hasil scan?)")
                    continue
                if replace:
                    store.delete_document(source)
                n = store.add_documents(chunks, source=source)
                ok += 1
                total_chunks += n
                print(f"  ✔ {path.name}: {n} chunk")
            except Exception as exc:
                failed += 1
                print(f"  ✗ {path.name}: {exc}")
        return {
            "found": len(files),
            "skipped": skipped,
            "indexed": ok,
            "failed": failed,
            "chunks": total_chunks,
        }
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk index semua dokumen (PDF/MD/TXT) dalam satu folder"
    )
    parser.add_argument("folder", help="Folder berisi dokumen")
    parser.add_argument(
        "--recursive", action="store_true", help="Telusuri subfolder juga"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Index ulang walau file sudah terindeks (replace chunk lama)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hanya tampilkan daftar file yang akan di-index, tanpa memproses",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        parser.error(f"Folder tidak ditemukan: {folder}")

    print(f"Memindai {folder} ({'rekursif' if args.recursive else 'non-rekursif'})...")
    stats = bulk_index(folder, recursive=args.recursive, replace=args.replace, dry_run=args.dry_run)

    if args.dry_run:
        print(
            f"\n{stats['found']} file ditemukan — {stats['skipped']} sudah terindeks, "
            f"{stats['found'] - stats['skipped']} akan di-index."
        )
        return

    print(
        f"\nSelesai: {stats['indexed']} terindeks, {stats['failed']} gagal, "
        f"{stats['skipped']} skip (sudah ada), {stats['chunks']} chunk total."
    )


if __name__ == "__main__":
    main()
