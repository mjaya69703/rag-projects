"""Database connection manager and schema definitions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def now_utc() -> str:
    """Return current ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create a thread-safe SQLite connection with WAL & Foreign Keys."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


CORE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    ip          TEXT NOT NULL DEFAULT '',
    status      INTEGER NOT NULL,
    duration_ms REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documents (
    source     TEXT PRIMARY KEY,
    job_id     TEXT NOT NULL DEFAULT '',
    kind       TEXT NOT NULL DEFAULT 'file',
    file_path  TEXT NOT NULL DEFAULT '',
    checksum   TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    category   TEXT NOT NULL DEFAULT 'Umum',
    status     TEXT NOT NULL DEFAULT 'queued',
    chunks     INTEGER NOT NULL DEFAULT 0,
    error      TEXT NOT NULL DEFAULT '',
    version    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS glossary_terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term        TEXT NOT NULL COLLATE NOCASE UNIQUE,
    definition  TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    page        INTEGER,
    category    TEXT NOT NULL DEFAULT 'Umum',
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_cards (
    card_id       TEXT PRIMARY KEY,
    question      TEXT NOT NULL,
    source        TEXT,
    created_at    TEXT NOT NULL,
    last_reviewed TEXT,
    next_due      TEXT NOT NULL,
    interval_days INTEGER NOT NULL DEFAULT 1,
    lapses        INTEGER NOT NULL DEFAULT 0,
    ease_factor   REAL NOT NULL DEFAULT 2.5,
    repetitions   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quiz_scores (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT,
    score      INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id              TEXT PRIMARY KEY,
    source          TEXT,
    questions_json  TEXT NOT NULL,
    answer_key_json TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flashcard_stats (
    heading       TEXT PRIMARY KEY,
    source        TEXT,
    known_count   INTEGER NOT NULL DEFAULT 0,
    unknown_count INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS annotations (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    chunk_id    TEXT NOT NULL,
    page        INTEGER,
    text        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def init_database(db_path: str | Path) -> None:
    """Initialize all SQLite tables idempotently."""
    with get_connection(db_path) as conn:
        conn.executescript(CORE_SCHEMA)
