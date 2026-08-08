"""Database SQLite: sessions, messages, session_summaries.

Koneksi dibuat per-operasi (aman untuk FastAPI threadpool). Semua
timestamp disimpan sebagai ISO-8601 UTC.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _conn(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # aktifkan ON DELETE CASCADE
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT 'New Chat',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    sources    TEXT,               -- JSON list of source dicts
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id         TEXT PRIMARY KEY,
    summary_text       TEXT NOT NULL,
    last_message_index INTEGER NOT NULL,
    created_at         TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deleted_documents (
    source     TEXT PRIMARY KEY,
    deleted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_categories (
    source     TEXT PRIMARY KEY,
    category   TEXT NOT NULL DEFAULT 'Umum',
    updated_at TEXT NOT NULL
);
"""


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _conn(db_path) as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------------
# Sessions
# ----------------------------------------------------------------------
def create_session(db_path: str | Path, title: str = "New Chat") -> dict:
    session_id = uuid.uuid4().hex
    now = _now()
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, title, now, now),
        )
    return {"id": session_id, "title": title, "created_at": now, "updated_at": now}


def list_sessions(db_path: str | Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions "
            "ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(db_path: str | Path, session_id: str) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def rename_session(db_path: str | Path, session_id: str, title: str) -> bool:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title.strip() or "New Chat", _now(), session_id),
        )
    return cur.rowcount > 0


def delete_session(db_path: str | Path, session_id: str) -> bool:
    with _conn(db_path) as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return cur.rowcount > 0


def touch_session(db_path: str | Path, session_id: str) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
        )


# ----------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------
def add_message(
    db_path: str | Path,
    session_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> dict:
    now = _now()
    sources_json = json.dumps(sources or [], ensure_ascii=False)
    with _conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, sources, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, sources_json, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
    return {
        "id": cur.lastrowid,
        "session_id": session_id,
        "role": role,
        "content": content,
        "sources": sources or [],
        "created_at": now,
    }


def get_messages(
    db_path: str | Path, session_id: str, limit: int | None = None
) -> list[dict]:
    sql = (
        "SELECT id, session_id, role, content, sources, created_at "
        "FROM messages WHERE session_id = ? ORDER BY id"
    )
    params: tuple = (session_id,)
    if limit is not None:
        # ambil N pesan TERAKHIR: subquery id terbesar
        sql = (
            "SELECT id, session_id, role, content, sources, created_at FROM messages "
            "WHERE session_id = ? AND id IN "
            "(SELECT id FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?) "
            "ORDER BY id"
        )
        params = (session_id, session_id, limit)
    with _conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["sources"] = json.loads(d["sources"] or "[]")
        except json.JSONDecodeError:
            d["sources"] = []
        out.append(d)
    return out


def message_count(db_path: str | Path, session_id: str) -> int:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
    return row["c"]


def repeated_questions(
    db_path: str | Path,
    days: int = 7,
    min_hits: int = 2,
) -> list[dict]:
    """Pertanyaan user yang diajukan berulang dalam N hari terakhir.

    Termometer perilaku (read-only): agregasi tabel messages yang sudah
    ada, tanpa tabel baru. Dipakai untuk memvalidasi asumsi "user sering
    menanyakan hal yang sama" sebelum memutuskan membangun fitur review
    / spaced repetition.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT MAX(content) AS question, COUNT(*) AS count, "
            "MAX(created_at) AS last_asked "
            "FROM messages "
            "WHERE role = 'user' AND created_at >= ? "
            "GROUP BY LOWER(TRIM(content)) HAVING COUNT(*) >= ? "
            "ORDER BY count DESC, last_asked DESC",
            (cutoff, min_hits),
        ).fetchall()
    return [dict(r) for r in rows]


def usage_summary(db_path: str | Path, days: int = 7) -> dict:
    """Ringkasan pemakaian N hari terakhir — konteks baca termometer.

    Memisahkan dua interpretasi list kosong: "app tidak dipakai" vs
    "dipakai tapi tidak ada pertanyaan yang diulang".
    """
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with _conn(db_path) as conn:
        sessions = conn.execute(
            "SELECT COUNT(DISTINCT session_id) AS n FROM messages "
            "WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()["n"]
        questions = conn.execute(
            "SELECT COUNT(*) AS n FROM messages "
            "WHERE role = 'user' AND created_at >= ?",
            (cutoff,),
        ).fetchone()["n"]
    return {"sessions_active": sessions, "questions": questions}


# ----------------------------------------------------------------------
# Dokumen yang dihapus (grounding: bedakan "dihapus" vs "tidak ada")
# ----------------------------------------------------------------------
def record_deleted_document(db_path: str | Path, source: str) -> None:
    """Catat dokumen yang baru dihapus dari indeks."""
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deleted_documents (source, deleted_at) "
            "VALUES (?, ?)",
            (source, _now()),
        )


def clear_deleted_document(db_path: str | Path, source: str) -> None:
    """Hapus catatan deleted — dipanggil saat dokumen di-upload ulang."""
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM deleted_documents WHERE source = ?", (source,))


def list_deleted_documents(db_path: str | Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT source, deleted_at FROM deleted_documents "
            "ORDER BY deleted_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def estimate_tokens(db_path: str | Path, session_id: str) -> int:
    """Estimasi token seluruh pesan di session (~4 char/token)."""
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT SUM(LENGTH(content)) AS total FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    total_chars = row["total"] or 0
    return total_chars // 4


# ----------------------------------------------------------------------
# Summaries
# ----------------------------------------------------------------------
def save_summary(
    db_path: str | Path,
    session_id: str,
    summary_text: str,
    last_message_index: int,
) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT INTO session_summaries (session_id, summary_text, last_message_index, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "summary_text = excluded.summary_text, "
            "last_message_index = excluded.last_message_index, "
            "created_at = excluded.created_at",
            (session_id, summary_text, last_message_index, _now()),
        )


def get_summary(db_path: str | Path, session_id: str) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT session_id, summary_text, last_message_index, created_at "
            "FROM session_summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


# ----------------------------------------------------------------------
# Categories & Grouping
# ----------------------------------------------------------------------
def set_document_category(db_path: str | Path, source: str, category: str) -> None:
    cat = category.strip() or "Umum"
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT INTO document_categories (source, category, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(source) DO UPDATE SET category = excluded.category, updated_at = excluded.updated_at",
            (source, cat, _now()),
        )


def get_document_category(db_path: str | Path, source: str) -> str:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT category FROM document_categories WHERE source = ?", (source,)
        ).fetchone()
    return row["category"] if row else "Umum"


def list_document_categories(db_path: str | Path) -> dict[str, str]:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT source, category FROM document_categories").fetchall()
    return {r["source"]: r["category"] for r in rows}


def list_all_categories(db_path: str | Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT category, COUNT(source) as doc_count FROM document_categories GROUP BY category ORDER BY category ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document_category_mapping(db_path: str | Path, source: str) -> None:
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM document_categories WHERE source = ?", (source,))

