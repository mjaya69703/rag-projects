"""Learning, Spaced Repetition, Quiz, and Flashcard repository."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional
from app.Repositories.BaseRepository import BaseRepository


class LearningRepository(BaseRepository):
    """Repository handling review cards (SM-2), quiz attempts/scores, and flashcard stats."""

    # ------------------------------------------------------------------
    # Review Cards (SM-2)
    # ------------------------------------------------------------------
    def get_review_card(self, card_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM review_cards WHERE card_id = ?", (card_id,)).fetchone()
        return dict(row) if row else None

    def upsert_review_card(
        self,
        card_id: str,
        question: str,
        source: str | None = None,
        interval_days: int = 1,
        ease_factor: float = 2.5,
        repetitions: int = 0,
        lapses: int = 0,
        next_due: str | None = None,
        last_reviewed: str | None = None,
    ) -> None:
        now = self.now
        due = next_due or now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO review_cards "
                "(card_id, question, source, created_at, last_reviewed, next_due, "
                " interval_days, lapses, ease_factor, repetitions) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(card_id) DO UPDATE SET "
                "question = excluded.question, "
                "source = excluded.source, "
                "last_reviewed = excluded.last_reviewed, "
                "next_due = excluded.next_due, "
                "interval_days = excluded.interval_days, "
                "lapses = excluded.lapses, "
                "ease_factor = excluded.ease_factor, "
                "repetitions = excluded.repetitions",
                (card_id, question, source, now, last_reviewed, due,
                 interval_days, lapses, ease_factor, repetitions),
            )

    def list_due_cards(self, limit: int = 20) -> list[dict]:
        now = self.now
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM review_cards WHERE next_due <= ? ORDER BY next_due ASC LIMIT ?",
                (now, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_all_cards(self, source: str | None = None) -> list[dict]:
        with self.get_conn() as conn:
            if source:
                rows = conn.execute("SELECT * FROM review_cards WHERE source = ?", (source,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM review_cards").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Quiz Scores & Server-side Attempts
    # ------------------------------------------------------------------
    def record_quiz_score(self, source: str | None, score: int, total: int) -> int:
        now = self.now
        with self.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO quiz_scores (source, score, total, created_at) VALUES (?, ?, ?, ?)",
                (source, score, total, now),
            )
            return int(cur.lastrowid)

    def list_quiz_scores(self, source: str | None = None, limit: int = 20) -> list[dict]:
        with self.get_conn() as conn:
            if source:
                rows = conn.execute(
                    "SELECT id, source, score, total, created_at FROM quiz_scores "
                    "WHERE source = ? ORDER BY id DESC LIMIT ?",
                    (source, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, source, score, total, created_at FROM quiz_scores "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def save_quiz_attempt(
        self,
        attempt_id: str,
        source: str | None,
        questions_json: str,
        answer_key_json: str,
    ) -> None:
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO quiz_attempts (id, source, questions_json, answer_key_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (attempt_id, source, questions_json, answer_key_json, now),
            )

    def get_quiz_attempt(self, attempt_id: str) -> dict | None:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM quiz_attempts WHERE id = ?", (attempt_id,)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Flashcard Stats
    # ------------------------------------------------------------------
    def record_flashcard_stat(self, heading: str, source: str | None, known: bool) -> None:
        now = self.now
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO flashcard_stats (heading, source, known_count, unknown_count, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(heading) DO UPDATE SET "
                "source = CASE WHEN excluded.source IS NOT NULL THEN excluded.source ELSE flashcard_stats.source END, "
                "known_count = flashcard_stats.known_count + excluded.known_count, "
                "unknown_count = flashcard_stats.unknown_count + excluded.unknown_count, "
                "updated_at = excluded.updated_at",
                (heading, source, 1 if known else 0, 0 if known else 1, now),
            )

    def list_flashcard_stats(self, source: str | None = None) -> list[dict]:
        with self.get_conn() as conn:
            if source:
                rows = conn.execute(
                    "SELECT heading, source, known_count, unknown_count, updated_at "
                    "FROM flashcard_stats WHERE source = ?",
                    (source,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT heading, source, known_count, unknown_count, updated_at FROM flashcard_stats"
                ).fetchall()
        return [dict(r) for r in rows]
