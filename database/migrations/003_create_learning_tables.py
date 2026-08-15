"""Migration 003: Create Learning Loop tables (SM-2, Quizzes, Flashcards)."""

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS review_cards (
            card_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            source TEXT,
            next_due TEXT NOT NULL DEFAULT (datetime('now')),
            interval_days REAL NOT NULL DEFAULT 1.0,
            ease_factor REAL NOT NULL DEFAULT 2.5,
            repetitions INTEGER NOT NULL DEFAULT 0,
            lapses INTEGER NOT NULL DEFAULT 0,
            last_reviewed TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            attempt_id TEXT PRIMARY KEY,
            source TEXT,
            answer_key_json TEXT NOT NULL,
            total_questions INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flashcard_stats (
            heading TEXT NOT NULL,
            source TEXT,
            known_count INTEGER NOT NULL DEFAULT 0,
            unknown_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (heading, source)
        )
    """)


def down(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS flashcard_stats")
    conn.execute("DROP TABLE IF EXISTS quiz_attempts")
    conn.execute("DROP TABLE IF EXISTS quiz_scores")
    conn.execute("DROP TABLE IF EXISTS review_cards")
