"""Migration 004: Create Annotations and Glossary tables."""

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            page INTEGER,
            text TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS glossary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL UNIQUE,
            definition TEXT NOT NULL,
            source TEXT NOT NULL,
            page INTEGER,
            category TEXT NOT NULL DEFAULT 'Umum',
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_glossary_term ON glossary(term)")


def down(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS glossary")
    conn.execute("DROP TABLE IF EXISTS annotations")
