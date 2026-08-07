"""Annotations (fitur #9): catatan pribadi yang menempel pada chunk dokumen.

Identitas chunk = "source#chunk_index" (stabil di ChromaDB karena ID
deterministik). Catatan ditampilkan ulang setiap chunk yang sama terbawa
ke dalam jawaban — jadi materi yang sudah kamu tandai tetap dikenali.

Schema punya sendiri (CREATE TABLE IF NOT EXISTS) — tidak menyentuh db.py.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _conn(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS annotations (
            chunk_key  TEXT PRIMARY KEY,
            note       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


def chunk_key(source: str, chunk_index: int) -> str:
    return f"{source}#{chunk_index}"


def upsert_note(db_path: str | Path, key: str, note: str) -> dict:
    """Simpan/ubah catatan untuk satu chunk. note kosong = hapus."""
    now = _now()
    with _conn(db_path) as conn:
        if not note.strip():
            conn.execute("DELETE FROM annotations WHERE chunk_key = ?", (key,))
            return {"chunk_key": key, "note": ""}
        conn.execute(
            "INSERT INTO annotations (chunk_key, note, created_at, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chunk_key) DO UPDATE SET note = excluded.note, "
            "updated_at = excluded.updated_at",
            (key, note.strip(), now, now),
        )
        return {"chunk_key": key, "note": note.strip()}


def get_note(db_path: str | Path, key: str) -> str:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT note FROM annotations WHERE chunk_key = ?", (key,)
        ).fetchone()
    return row["note"] if row else ""


def list_annotations(db_path: str | Path, limit: int = 200) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT chunk_key, note, created_at, updated_at FROM annotations "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
