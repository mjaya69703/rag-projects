"""Migration 002: Create Documents, Categories, and Audit tables."""

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            source TEXT PRIMARY KEY,
            job_id TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'file',
            file_path TEXT NOT NULL DEFAULT '',
            checksum TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            category TEXT NOT NULL DEFAULT 'Umum',
            status TEXT NOT NULL DEFAULT 'queued',
            chunks INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deleted_documents (
            source TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now')),
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            ip TEXT NOT NULL DEFAULT '',
            status INTEGER NOT NULL,
            duration_ms REAL NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_categories (
            source TEXT PRIMARY KEY,
            category TEXT NOT NULL DEFAULT 'Umum',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def down(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS document_categories")
    conn.execute("DROP TABLE IF EXISTS audit_log")
    conn.execute("DROP TABLE IF EXISTS deleted_documents")
    conn.execute("DROP TABLE IF EXISTS documents")
