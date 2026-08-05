"""Database SQLite: sessions, messages, session_summaries.

Koneksi dibuat per-operasi (aman untuk FastAPI threadpool). Semua
timestamp disimpan sebagai ISO-8601 UTC.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
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
