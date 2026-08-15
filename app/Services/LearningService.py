"""Learning Service: Spaced repetition (SM-2), Quiz generation & deterministic grading, Flashcards, and Weak Spots."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.Repositories.LearningRepository import LearningRepository
from app.Repositories.SessionRepository import SessionRepository
from app.Repositories.VectorRepository import VectorRepository
from app.Services.LlmService import LlmService

logger = logging.getLogger(__name__)

SM2_MIN_EASE = 1.3
SM2_INITIAL_EASE = 2.5
SM2_EASE_INC = 0.1
SM2_EASE_DEC = 0.2
SM2_INTERVALS = {1: 1, 2: 6}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else default


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _parse_json_array(text: str) -> list[Any] | None:
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        pass
    cleaned = _strip_code_fence(text).strip()
    if cleaned != text:
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return None


def _parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    cleaned = _strip_code_fence(text).strip()
    if cleaned != text:
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def _parse_questions(text: str) -> list[dict]:
    data = _parse_json_array(text)
    if not data:
        return []
    questions: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        if not isinstance(options, list) or len(options) < 2:
            continue
        question = str(item.get("question", "")).strip()
        if not question:
            continue
        questions.append(
            {
                "question": question,
                "options": [str(o) for o in options[:4]],
                "answer_index": max(
                    0, min(_as_int(item.get("answer_index"), 0), len(options) - 1)
                ),
            }
        )
    return questions


class LearningService:
    """Service orchestrating learning loops, flashcards, SM-2 spaced repetition, and quizzes."""

    def __init__(
        self,
        learning_repo: LearningRepository,
        vector_repo: VectorRepository,
        llm: LlmService | None = None,
        session_repo: SessionRepository | None = None,
    ) -> None:
        self.learning_repo = learning_repo
        self.vector_repo = vector_repo
        self.llm = llm or LlmService()
        self.session_repo = session_repo

    # ------------------------------------------------------------------
    # Spaced Repetition (SM-2)
    # ------------------------------------------------------------------
    def due_cards(self, limit: int = 10) -> list[dict]:
        return self.learning_repo.list_due_cards(limit=limit)

    def answer_card(self, card_id: str, remembered: bool) -> dict:
        row = self.learning_repo.get_review_card(card_id)
        if row is None:
            raise ValueError(f"Kartu tidak ditemukan: {card_id}")

        ease = float(row.get("ease_factor") or SM2_INITIAL_EASE)
        reps = int(row.get("repetitions") or 0)
        if remembered:
            reps += 1
            if reps == 1:
                interval = SM2_INTERVALS[1]
            elif reps == 2:
                interval = SM2_INTERVALS[2]
            else:
                interval = round(max(1, int(row.get("interval_days") or 1) * ease))
            ease = max(SM2_MIN_EASE, ease + SM2_EASE_INC)
            lapses = row.get("lapses", 0)
        else:
            interval = 1
            reps = 0
            ease = max(SM2_MIN_EASE, ease - SM2_EASE_DEC)
            lapses = row.get("lapses", 0) + 1

        next_due = (datetime.now(UTC) + timedelta(days=interval)).isoformat()
        last_reviewed = datetime.now(UTC).isoformat()

        self.learning_repo.upsert_review_card(
            card_id=card_id,
            question=row["question"],
            source=row.get("source"),
            interval_days=interval,
            ease_factor=ease,
            repetitions=reps,
            lapses=lapses,
            next_due=next_due,
            last_reviewed=last_reviewed,
        )
        return self.learning_repo.get_review_card(card_id) or {}

    def card_stats(self) -> dict:
        tomorrow_midnight = (datetime.now(UTC) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        cards = self.learning_repo.list_all_cards()
        total = len(cards)
        due = sum(1 for c in cards if c["next_due"] < tomorrow_midnight)
        avg = (sum(c["lapses"] for c in cards) / total) if total > 0 else 0.0
        return {"total": total, "due_today": due, "avg_lapses": round(avg, 2)}

    # ------------------------------------------------------------------
    # Quiz Generation & Deterministic Grading
    # ------------------------------------------------------------------
    def generate_quiz(self, source: str | None = None, n: int = 5) -> list[dict]:
        where = {"source": source} if source else None
        chunks = self.vector_repo.get_by_source(source) if source else self.vector_repo.list_all_chunks()
        
        chosen = []
        seen_headings = set()
        for item in chunks:
            heading = item.get("metadata", {}).get("heading") or "Intro"
            if heading in seen_headings:
                continue
            seen_headings.add(heading)
            chosen.append({"text": item["text"], "heading": heading})
            if len(chosen) >= n:
                break
        if not chosen:
            return []

        material = "\n\n".join(
            f"[{i + 1}] ({c['heading']})\n{c['text']}"
            for i, c in enumerate(chosen)
        )
        prompt = (
            "Buat soal pilihan ganda berbahasa Indonesia berdasarkan materi "
            "berikut. Keluarkan HANYA JSON array, tanpa teks lain. Format tiap "
            'soal: {"question": "...", "options": ["a", "b", "c", "d"], '
            '"answer_index": 0} dengan answer_index 0-3 menunjuk jawaban benar '
            f"dari 4 opsi. Buat tepat {n} soal.\n\nMATERI:\n{material}"
        )
        try:
            response = self.llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=min(2048, max(512, n * 220)),
            )
            questions = _parse_questions(response.text)
            if questions:
                return questions
        except Exception as exc:
            logger.warning("LLM quiz generation failed: %s", exc)

        heading = chosen[0]["heading"]
        return [
            {
                "question": f"Bagian '{heading}' membahas topik apa?",
                "options": [heading, "Topik lain", "Tidak dibahas", "Tidak tahu"],
                "answer_index": 0,
            }
        ]

    def create_quiz_attempt(self, source: str | None, questions: list[dict]) -> dict:
        attempt_id = uuid.uuid4().hex
        safe = [
            {
                "question": q.get("question"),
                "options": list(q.get("options") or []),
            }
            for q in questions
        ]
        key = [int(q.get("answer_index", 0)) for q in questions]
        self.learning_repo.save_quiz_attempt(
            attempt_id=attempt_id,
            source=source,
            questions_json=json.dumps(safe, ensure_ascii=False),
            answer_key_json=json.dumps(key, ensure_ascii=False),
        )
        return {"attempt_id": attempt_id, "source": source, "questions": safe}

    def grade_quiz_attempt(self, attempt_id: str, answers: list[int]) -> dict:
        row = self.learning_repo.get_quiz_attempt(attempt_id)
        if row is None:
            raise ValueError("Attempt kuis tidak ditemukan.")
        questions = json.loads(row["questions_json"] or "[]")
        key = json.loads(row["answer_key_json"] or "[]")

        if len(answers) != len(questions):
            raise ValueError(
                f"Jumlah jawaban ({len(answers)}) != jumlah soal ({len(questions)})."
            )

        details = [
            {
                "question": (q or {}).get("question", ""),
                "correct": (answers[i] == key[i]) if i < len(key) else False,
                "correct_index": key[i] if i < len(key) else -1,
            }
            for i, q in enumerate(questions)
        ]
        score = sum(1 for d in details if d["correct"])
        total = len(questions)
        self.learning_repo.record_quiz_score(row.get("source"), score, total)
        return {
            "score": score,
            "total": total,
            "correct": [i for i, d in enumerate(details) if d["correct"]],
            "details": details,
        }

    def quiz_history(self, limit: int = 20) -> list[dict]:
        return self.learning_repo.list_quiz_scores(limit=limit)

    # ------------------------------------------------------------------
    # Flashcards
    # ------------------------------------------------------------------
    def flashcards(self, source: str | None = None, limit: int = 20) -> list[dict]:
        chunks = self.vector_repo.get_by_source(source) if source else self.vector_repo.list_all_chunks()
        by_heading: dict[str, str] = {}
        for item in chunks:
            heading = item.get("metadata", {}).get("heading") or "Intro"
            if heading not in by_heading:
                by_heading[heading] = item["text"]
        out = [{"heading": h, "content": c} for h, c in by_heading.items()]
        out.sort(key=lambda e: e["heading"])
        return out[:limit]

    def answer_flashcard(self, heading: str, source: str, known: bool) -> dict:
        self.learning_repo.record_flashcard_stat(heading, source, known)
        stats = self.learning_repo.list_flashcard_stats(source=source)
        for s in stats:
            if s["heading"] == heading:
                return s
        return {"heading": heading, "source": source, "known_count": 1 if known else 0, "unknown_count": 0 if known else 1}

    def flashcard_stats(self, limit: int = 50) -> list[dict]:
        return self.learning_repo.list_flashcard_stats()[:limit]

    # ------------------------------------------------------------------
    # Weak-Spots & Mastery
    # ------------------------------------------------------------------
    def weak_spots(self, limit: int = 8) -> list[dict]:
        entries: dict[str, dict] = {}
        cards = self.learning_repo.list_all_cards()
        for card in cards:
            key = card["question"].strip().lower()
            entry = entries.setdefault(
                key,
                {"topic": card["question"], "asked": 0, "lapses": 0, "wrong": 0},
            )
            entry["lapses"] += card.get("lapses", 0)
            entry["wrong"] += card.get("lapses", 0)

        fcards = self.learning_repo.list_flashcard_stats()
        for f in fcards:
            topic = f"{f['heading']} ({f.get('source') or 'Doc'})"
            entry = entries.setdefault(
                topic.lower(),
                {"topic": topic, "asked": 0, "lapses": 0, "wrong": 0},
            )
            entry["asked"] += f["known_count"] + f["unknown_count"]
            entry["wrong"] += f["unknown_count"]

        quizzes = self.learning_repo.list_quiz_scores(limit=100)
        for q in quizzes:
            topic = f"Quiz: {q.get('source') or 'General'}"
            entry = entries.setdefault(
                topic.lower(),
                {"topic": topic, "asked": 0, "lapses": 0, "wrong": 0},
            )
            entry["asked"] += q["total"]
            entry["wrong"] += max(0, q["total"] - q["score"])

        for entry in entries.values():
            entry["score"] = entry["asked"] + entry["lapses"] * 2 + entry["wrong"] * 3
        ranked = sorted(entries.values(), key=lambda e: (-e["score"], e["topic"]))
        return ranked[:limit]

    def mastery_stats(self) -> list[dict]:
        stats: dict[str, dict] = {}

        def bump(source: str, asked: int = 0, correct: int = 0, wrong: int = 0) -> None:
            entry = stats.setdefault(
                source, {"exposure": 0, "correct": 0, "wrong": 0, "mastery": 0.0}
            )
            entry["exposure"] += asked
            entry["correct"] += correct
            entry["wrong"] += wrong

        for f in self.learning_repo.list_flashcard_stats():
            bump(
                f.get("source") or "Umum",
                asked=f["known_count"] + f["unknown_count"],
                correct=f["known_count"],
                wrong=f["unknown_count"],
            )
        for q in self.learning_repo.list_quiz_scores(limit=200):
            bump(
                q.get("source") or "Umum",
                asked=q["total"],
                correct=q["score"],
                wrong=max(0, q["total"] - q["score"]),
            )
        for c in self.learning_repo.list_all_cards():
            bump(
                c.get("source") or "Umum",
                asked=max(int(c.get("repetitions") or 0), 1),
                wrong=int(c.get("lapses") or 0),
            )

        out = []
        for source, s in stats.items():
            answered = s["correct"] + s["wrong"]
            s["mastery"] = round(s["correct"] / answered, 2) if answered else 0.0
            out.append({"source": source, **s})
        out.sort(key=lambda e: (e["mastery"], -e["exposure"]))
        return out
