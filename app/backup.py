"""Backup & restore data lokal (SQLite + ChromaDB) sebagai ZIP portabel.

- ``create_backup``: snapshot SQLite (konsisten via sqlite3 backup API),
  salin direktori ChromaDB, tulis manifest, lalu bungkus jadi ZIP.
- ``restore_backup``: validasi & ekstrak ZIP, impor ulang isi SQLite
  (tidak menimpa file yang sedang terbuka), lalu transfer isi koleksi
  ChromaDB ke client yang sedang berjalan (anti file-lock di Windows).
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path

from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
DB_NAME = "chat.db"
CHROMA_DIR = "chroma"
BACKUP_VERSION = 1


def _manifest(settings) -> dict:
    return {
        "version": BACKUP_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": str(settings.db_path),
        "persist_dir": str(settings.persist_dir),
    }


def create_backup(settings, dest_dir: str | Path) -> Path:
    """Buat ZIP backup lengkap di dest_dir. Return path ZIP."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    zip_path = dest / f"rag-backup-{stamp}.zip"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        manifest = _manifest(settings)

        # 1) Snapshot SQLite yang konsisten (aman walau DB sedang terbuka).
        db_snapshot = tmp_path / DB_NAME
        src = sqlite3.connect(str(settings.db_path))
        try:
            dst = sqlite3.connect(str(db_snapshot))
            try:
                src.backup(dst)
                manifest["db_bytes"] = db_snapshot.stat().st_size
            finally:
                dst.close()
        finally:
            src.close()

        # 2) Salin direktori ChromaDB.
        chroma_copy = tmp_path / CHROMA_DIR
        if Path(settings.persist_dir).exists():
            shutil.copytree(settings.persist_dir, chroma_copy)
        manifest["chroma_bytes"] = sum(
            f.stat().st_size for f in chroma_copy.rglob("*") if f.is_file()
        )

        # 3) Manifest + zip.
        (tmp_path / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmp_path.iterdir():
                if f.is_dir():
                    for p in f.rglob("*"):
                        if p.is_file():
                            zf.write(p, f"{f.name}/{p.relative_to(f)}")
                else:
                    zf.write(f, f.name)
    logger.info("backup selesai: %s (%d entri, manifest %s)", zip_path, len(manifest), manifest)
    return zip_path


def _safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    """Ekstrak dengan perlindungan zip-slip (path traversal)."""
    for member in zf.infolist():
        name = Path(member.filename)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError(f"Entri backup tidak aman: {member.filename}")
        member_path = (target / name).resolve()
        if not str(member_path).startswith(str(target.resolve())):
            raise ValueError(f"Entri backup di luar direktori: {member.filename}")
        if member.is_dir():
            member_path.mkdir(parents=True, exist_ok=True)
        else:
            member_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(member_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def _restore_sqlite(live_path: str | Path, restored_db: str | Path) -> int:
    """Impor isi DB hasil restore ke DB live (anti file-lock)."""
    src = sqlite3.connect(str(restored_db))
    try:
        dst = sqlite3.connect(str(live_path), timeout=30)
        try:
            src.backup(dst)
            dst.execute("PRAGMA busy_timeout = 10000")
            dst.execute("PRAGMA journal_mode = WAL")
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()
    return 1


def _restore_chroma(live_store: VectorStore, restored_chroma: Path) -> int:
    """Transfer isi semua collection ChromaDB dari backup ke client live."""
    import chromadb
    from chromadb.config import Settings

    if not restored_chroma.exists():
        return 0
    backup_client = chromadb.PersistentClient(
        path=str(restored_chroma),
        settings=Settings(anonymized_telemetry=False),
    )
    total = 0
    for name in backup_client.list_collections():
        coll_name = name.name if hasattr(name, "name") else name
        try:
            src = backup_client.get_collection(coll_name)
        except Exception:
            continue
        data = src.get(include=["documents", "embeddings", "metadatas"])
        ids: list = data.get("ids") or []
        if not ids:
            continue
        docs = data.get("documents") or [None] * len(ids)
        embeddings = data.get("embeddings")
        metadatas = data.get("metadatas") or [None] * len(ids)
        has_embeddings = embeddings is not None and len(embeddings) > 0

        live_coll = live_store.client.get_or_create_collection(coll_name)
        stale = live_coll.get(include=[])["ids"]
        if stale:
            live_coll.delete(ids=stale)
        for i in range(0, len(ids), 500):
            chunk_ids = ids[i : i + 500]
            kwargs: dict = {
                "ids": chunk_ids,
                "documents": [docs[j] for j in range(i, min(i + 500, len(ids)))],
                "embeddings": (
                    [embeddings[j] for j in range(i, min(i + 500, len(ids)))]
                    if has_embeddings
                    else None
                ),
                "metadatas": [metadatas[j] for j in range(i, min(i + 500, len(ids)))],
            }
            if kwargs["embeddings"] is None:
                kwargs.pop("embeddings")
            live_coll.upsert(**{k: v for k, v in kwargs.items() if v is not None})
        total += len(ids)
    return total


def restore_backup(settings, archive: bytes) -> dict:
    """Terapkan isi ZIP backup ke penyimpanan live. Return ringkasan."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        zf = zipfile.ZipFile(__import__("io").BytesIO(archive))
        try:
            _safe_extract(zf, tmp_path)
        finally:
            zf.close()

        manifest_file = tmp_path / MANIFEST_NAME
        if not manifest_file.exists():
            raise ValueError("Backup tidak valid: manifest.json tidak ditemukan.")
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if manifest.get("version") != BACKUP_VERSION:
            raise ValueError(
                f"Versi backup tidak dikenal: {manifest.get('version')} (harus {BACKUP_VERSION})."
            )

        restored_db = tmp_path / DB_NAME
        restored_chroma = tmp_path / CHROMA_DIR
        result = {
            "status": "ok",
            "sqlite": 0,
            "chroma_entries": 0,
            "manifest": manifest,
        }
        if restored_db.exists():
            result["sqlite"] = _restore_sqlite(settings.db_path, restored_db)
        if restored_chroma.exists():
            store = VectorStore(persist_dir=settings.persist_dir)
            try:
                result["chroma_entries"] = _restore_chroma(store, restored_chroma)
            finally:
                store.close()
    logger.info("restore selesai: %s", result)
    return result