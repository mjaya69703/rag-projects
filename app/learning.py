"""Fitur belajar: spaced repetition, weak-spot, progress, quiz, flashcards.

Modul ini punya tabel SQLite sendiri (review_cards, quiz_scores) yang
dibuat idempotent via ``ensure_tables`` / ``_conn_learning`` — tidak
menyentuh schema di app/db.py. Semua timestamp ISO-8601 UTC (sama
dengan konvensi db.py).
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app import db
from app.db import _now

LEARNING_SCHEMA = """
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

-- Attempt kuis server-side (P2-04): soal + kunci jawaban disimpan di
-- server, skor dihitung deterministik — LLM tidak menentukan nilai.
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
"""

# Konstanta SM-2 (P2-03): ease factor, interval per repetition count.
SM2_MIN_EASE = 1.3
SM2_INITIAL_EASE = 2.5
SM2_EASE_INC = 0.1
SM2_EASE_DEC = 0.2
# Interval (hari) setelah repetition ke-1 dan ke-2; berikutnya interval * ease.
SM2_INTERVALS = {1: 1, 2: 6}


def _conn_learning(db_path: str | Path) -> sqlite3.Connection:
    """Koneksi SQLite dengan schema learning dijamin ada (idempotent)."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(LEARNING_SCHEMA)
    _migrate_review_cards(conn)
    return conn


def _migrate_review_cards(conn: sqlite3.Connection) -> None:
    """Tambah kolom SM-2 (ease_factor, repetitions) ke DB lama (idempotent)."""
    cols = {
        r["name"]
        for r in conn.execute("PRAGMA table_info(review_cards)").fetchall()
    }
    if "ease_factor" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN ease_factor REAL NOT NULL DEFAULT 2.5"
        )
    if "repetitions" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN repetitions INTEGER NOT NULL DEFAULT 0"
        )


def ensure_tables(db_path: str | Path) -> None:
    """Pastikan tabel milik modul learning ada (aman dipanggil berkali-kali)."""
    _conn_learning(db_path).close()


# ----------------------------------------------------------------------
# #1 Review mode / spaced repetition
# ----------------------------------------------------------------------
def sync_cards(db_path: str | Path) -> int:
    """Buat kartu review untuk pertanyaan berulang yang belum punya kartu.

    Sumber: ``db.repeated_questions()``. Kartu baru langsung due
    (next_due = sekarang). Return jumlah kartu yang dibuat.
    """
    now = _now()
    created = 0
    with _conn_learning(db_path) as conn:
        for row in db.repeated_questions(db_path):
            question = row["question"]
            exists = conn.execute(
                "SELECT 1 FROM review_cards WHERE LOWER(TRIM(question)) = ?",
                (question.strip().lower(),),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO review_cards (card_id, question, source, created_at, next_due) "
                "VALUES (?, ?, NULL, ?, ?)",
                (uuid.uuid4().hex, question, now, now),
            )
            created += 1
    return created


def due_cards(db_path: str | Path, limit: int = 10) -> list[dict]:
    """Kartu yang sudah waktunya diulang (next_due <= sekarang), urut due."""
    with _conn_learning(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM review_cards WHERE next_due <= ? "
            "ORDER BY next_due ASC LIMIT ?",
            (_now(), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def _sm2_schedule(row: sqlite3.Row, remembered: bool) -> tuple[int, int, float]:
    """(interval_days, repetitions, ease_factor) menurut SM-2 (P2-03).

    - Ingat: repetitions +1; interval 1 hari (rep 1), 6 hari (rep 2),
      lalu round(interval * ease); ease naik +0.1 (min 1.3).
    - Lupa : repetitions reset ke 0, interval kembali 1 hari, ease turun
      -0.2 (min 1.3). Lapses dihitung di pemanggil.
    """
    ease = float(row["ease_factor"] or SM2_INITIAL_EASE)
    reps = int(row["repetitions"] or 0)
    if remembered:
        reps += 1
        if reps == 1:
            interval = SM2_INTERVALS[1]
        elif reps == 2:
            interval = SM2_INTERVALS[2]
        else:
            interval = round(max(1, int(row["interval_days"] or 1) * ease))
        ease = max(SM2_MIN_EASE, ease + SM2_EASE_INC)
        return interval, reps, ease
    return 1, 0, max(SM2_MIN_EASE, ease - SM2_EASE_DEC)


def answer_card(db_path: str | Path, card_id: str, remembered: bool) -> dict:
    """Catat hasil review satu kartu (scheduler SM-2), kembalikan kartu baru.

    remembered: interval/ease naik sesuai SM-2; lapses di-reset ke 0.
    forgotten : interval kembali 1 hari, repetitions reset, lapses +1.
    """
    now = _now()
    with _conn_learning(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM review_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Kartu tidak ditemukan: {card_id}")
        interval, reps, ease = _sm2_schedule(row, remembered)
        lapses = row["lapses"] if remembered else row["lapses"] + 1
        next_due = (datetime.now(UTC) + timedelta(days=interval)).isoformat()
        conn.execute(
            "UPDATE review_cards SET interval_days = ?, repetitions = ?, "
            "ease_factor = ?, lapses = ?, last_reviewed = ?, next_due = ? "
            "WHERE card_id = ?",
            (interval, reps, ease, lapses, now, next_due, card_id),
        )
        updated = conn.execute(
            "SELECT * FROM review_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
    return dict(updated)


def card_stats(db_path: str | Path) -> dict:
    """Statistik kartu: total, due hari ini (termasuk yang telat), avg lapses."""
    tomorrow_midnight = (datetime.now(UTC) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    with _conn_learning(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM review_cards").fetchone()["n"]
        due = conn.execute(
            "SELECT COUNT(*) AS n FROM review_cards WHERE next_due < ?",
            (tomorrow_midnight,),
        ).fetchone()["n"]
        avg = conn.execute("SELECT AVG(lapses) AS a FROM review_cards").fetchone()["a"]
    return {"total": total, "due_today": due, "avg_lapses": round(avg or 0.0, 2)}


# ----------------------------------------------------------------------
# #2 Weak-spot detection
# ----------------------------------------------------------------------
def weak_spots(db_path: str | Path, limit: int = 8) -> list[dict]:
    """Topik paling lemah: frekuensi tanya ulang + bukti salah jawab nyata.

    Komponen ``wrong`` sekarang terisi sungguhan (P2-03) dari tiga sumber:
    - lapses kartu review (lupa saat spaced repetition)
    - jawaban "belum tahu" pada flashcard
    - jawaban salah pada kuis (per source)

    Skor = asked + lapses*2 + wrong*3.
    """
    entries: dict[str, dict] = {}
    for row in db.repeated_questions(db_path):
        key = row["question"].strip().lower()
        entries[key] = {
            "topic": row["question"],
            "asked": row["count"],
            "lapses": 0,
            "wrong": 0,
        }
    with _conn_learning(db_path) as conn:
        cards = conn.execute(
            "SELECT question, lapses FROM review_cards"
        ).fetchall()
    for card in cards:
        key = card["question"].strip().lower()
        entry = entries.setdefault(
            key,
            {"topic": card["question"], "asked": 0, "lapses": 0, "wrong": 0},
        )
        entry["lapses"] += card["lapses"]
        entry["wrong"] += card["lapses"]  # lupa = bukti lemah, bukan 0

    with _conn_learning(db_path) as conn:
        fcards = conn.execute(
            "SELECT heading, source, known_count, unknown_count "
            "FROM flashcard_stats"
        ).fetchall()
    for f in fcards:
        topic = f"{f['heading']} ({f['source']})"
        entry = entries.setdefault(
            topic.lower(),
            {"topic": topic, "asked": 0, "lapses": 0, "wrong": 0},
        )
        entry["asked"] += f["known_count"] + f["unknown_count"]
        entry["wrong"] += f["unknown_count"]

    with _conn_learning(db_path) as conn:
        quizes = conn.execute(
            "SELECT source, score, total FROM quiz_scores WHERE source IS NOT NULL"
        ).fetchall()
    for q in quizes:
        topic = f"Quiz: {q['source']}"
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


def mastery_stats(db_path: str | Path) -> list[dict]:
    """Mastery per source: exposure vs correctness vs mastery (P2-03).

    Membedakan metrik exposure (berapa sering diuji) dan correctness
    (berapa benar) — bukan cuma "sering ditanya". Mastery = benar / total.
    """
    stats: dict[str, dict] = {}

    def bump(source: str, asked: int = 0, correct: int = 0, wrong: int = 0) -> None:
        entry = stats.setdefault(
            source, {"exposure": 0, "correct": 0, "wrong": 0, "mastery": 0.0}
        )
        entry["exposure"] += asked
        entry["correct"] += correct
        entry["wrong"] += wrong

    with _conn_learning(db_path) as conn:
        for f in conn.execute(
            "SELECT source, known_count, unknown_count FROM flashcard_stats"
        ).fetchall():
            bump(
                f["source"] or "Umum",
                asked=f["known_count"] + f["unknown_count"],
                correct=f["known_count"],
                wrong=f["unknown_count"],
            )
        for q in conn.execute(
            "SELECT source, score, total FROM quiz_scores"
        ).fetchall():
            bump(
                q["source"] or "Umum",
                asked=q["total"],
                correct=q["score"],
                wrong=max(0, q["total"] - q["score"]),
            )
        for c in conn.execute(
            "SELECT source, lapses, repetitions FROM review_cards"
        ).fetchall():
            bump(
                c["source"] or "Umum",
                asked=max(int(c["repetitions"] or 0), 1),
                wrong=int(c["lapses"] or 0),
            )

    out = []
    for source, s in stats.items():
        answered = s["correct"] + s["wrong"]
        s["mastery"] = round(s["correct"] / answered, 2) if answered else 0.0
        out.append({"source": source, **s})
    out.sort(key=lambda e: (e["mastery"], -e["exposure"]))
    return out


# ----------------------------------------------------------------------
# #3 Progress tracking
# ----------------------------------------------------------------------
def document_progress(
    db_path: str | Path,
    headings_by_source: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Progress belajar per dokumen, dari heading yang pernah muncul di jawaban.

    Meng-agregasi ``messages.sources`` (via db.get_messages) per source:
    heading yang pernah dikutip + berapa kali, serta jumlah jawaban yang
    mengutip source tersebut. Tidak memanggil VectorStore — kalau
    ``headings_by_source`` diberikan, dokumen tanpa jejak di chat tetap
    ikut dilaporkan (headings_covered kosong).
    """
    progress: dict[str, dict] = {}
    for session in db.list_sessions(db_path):
        for msg in db.get_messages(db_path, session["id"]):
            if msg["role"] != "assistant":
                continue
            cited = {
                s.get("source")
                for s in msg["sources"] or []
                if s.get("source")
            }
            for name in cited:
                entry = progress.setdefault(
                    name,
                    {"headings_covered": {}, "total_questions": 0},
                )
                entry["total_questions"] += 1
                for s in msg["sources"]:
                    if s.get("source") == name and s.get("heading"):
                        h = s["heading"]
                        entry["headings_covered"][h] = (
                            entry["headings_covered"].get(h, 0) + 1
                        )

    out = [
        {
            "source": name,
            "headings_covered": [
                {"heading": h, "asked": c}
                for h, c in sorted(
                    e["headings_covered"].items(),
                    key=lambda kv: (-kv[1], kv[0]),
                )
            ],
            "total_questions": e["total_questions"],
        }
        for name, e in progress.items()
    ]
    if headings_by_source:
        seen = {e["source"] for e in out}
        out.extend(
            {"source": name, "headings_covered": [], "total_questions": 0}
            for name in headings_by_source
            if name not in seen
        )
    out.sort(key=lambda e: e["source"])
    return out


# ----------------------------------------------------------------------
# #4 Quiz generator + skor
# ----------------------------------------------------------------------
def generate_quiz(
    engine: Any, source: str | None = None, n: int = 5
) -> list[dict]:
    """Buat soal pilihan ganda dari chunk dokumen via LLM.

    Chunk diambil langsung dari ``store.collection.get`` (tanpa
    embedding), maks. satu chunk per heading. LLM diminta JSON array
    soal; kalau parsing gagal, fallback satu soal sederhana dari heading.
    """
    where = {"source": source} if source else None
    result = engine.store.collection.get(
        where=where, limit=n * 2, include=["documents", "metadatas"]
    )
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    chosen: list[dict] = []
    seen_headings: set[str] = set()
    for doc, meta in zip(documents, metadatas, strict=True):
        heading = (meta or {}).get("heading") or "Intro"
        if heading in seen_headings:
            continue
        seen_headings.add(heading)
        chosen.append({"text": doc, "heading": heading})
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
        response = engine.llm.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=min(2048, max(512, n * 220)),
        )
        questions = _parse_questions(response.text)
        if questions:
            return questions
    except Exception:
        pass

    heading = chosen[0]["heading"]
    return [
        {
            "question": f"Bagian '{heading}' membahas topik apa?",
            "options": [heading, "Topik lain", "Tidak dibahas", "Tidak tahu"],
            "answer_index": 0,
        }
    ]


def grade_quiz(
    engine: Any, questions: list[dict], answers: list[int]
) -> dict:
    """Koreksi jawaban kuis via LLM + review PER SOAL.

    Return:
        {"score", "total", "feedback",
         "details": [{"correct", "correct_index", "explanation"}]}
    detail per soal: benar/salah, index jawaban benar, penjelasan singkat.
    Fallback bila parsing JSON gagal: bandingkan answer_index langsung.
    """
    total = len(questions)
    if total == 0:
        return {"score": 0, "total": 0, "feedback": "", "details": []}

    lines: list[str] = []
    for i, q in enumerate(questions, 1):
        opts = "\n".join(
            f"  {j + 1}. {o}" for j, o in enumerate(q.get("options", []))
        )
        user_ans = answers[i - 1] if i - 1 < len(answers) else "-"
        lines.append(
            f"{i}. {q.get('question', '')}\n{opts}\n   Jawaban user: {user_ans}"
        )
    prompt = (
        "Koreksi jawaban kuis pilihan ganda berikut. Jawaban user adalah "
        "nomor opsi (1-based). Keluarkan HANYA JSON dengan bentuk:\n"
        '{"score": <jumlah benar>, "total": <jumlah soal>, '
        '"feedback": "<komentar singkat>", '
        '"details": [{"correct": true/false, "correct_index": <0-based>, '
        '"explanation": "<penjelasan singkat>"}]}\n'
        "details WAJIB berisi satu objek per soal, urut sama.\n\n"
        + "\n\n".join(lines)
    )
    try:
        response = engine.llm.chat(
            [{"role": "user", "content": prompt}], max_tokens=1024
        )
        data = _parse_json_object(response.text) or {}
        raw_details = data.get("details") or []

        # LLM tidak memberi detail valid -> koreksi deterministik (jangan
        # jatuh ke score 0 hanya karena parse kosong).
        if not raw_details:
            return _grade_deterministic(questions, answers, total)

        total_out = _as_int(data.get("total"), total) or total

        details: list[dict] = []
        for i, q in enumerate(questions):
            raw = (
                raw_details[i]
                if i < len(raw_details) and isinstance(raw_details[i], dict)
                else {}
            )
            correct_index = _as_int(raw.get("correct_index"), -1)
            if not 0 <= correct_index < len(q.get("options", [])):
                correct_index = int(q.get("answer_index", 0))
            user_ans = answers[i] if i < len(answers) else -1
            correct = user_ans == correct_index
            details.append(
                {
                    "correct": correct,
                    "correct_index": correct_index,
                    "explanation": str(raw.get("explanation", "")).strip(),
                }
            )
        score_out = max(0, min(_as_int(data.get("score"), 0), total_out))
        return {
            "score": score_out,
            "total": total_out,
            "feedback": str(data.get("feedback", "")).strip(),
            "details": details,
        }
    except Exception:
        return _grade_deterministic(questions, answers, total)


def _grade_deterministic(
    questions: list[dict], answers: list[int], total: int
) -> dict:
    """Fallback tanpa LLM: bandingkan jawaban user dengan kunci (answer_index)."""
    details = [
        {
            "correct": (
                answers[i] == int(q.get("answer_index", -1))
                if i < len(answers)
                else False
            ),
            "correct_index": int(q.get("answer_index", 0)),
            "explanation": "",
        }
        for i, q in enumerate(questions)
    ]
    return {
        "score": sum(1 for d in details if d["correct"]),
        "total": total,
        "feedback": "",
        "details": details,
    }


def save_quiz_score(
    db_path: str | Path, source: str | None, score: int, total: int
) -> dict:
    """Simpan hasil kuis ke tabel quiz_scores. Return baris yang tersimpan."""
    now = _now()
    with _conn_learning(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO quiz_scores (source, score, total, created_at) "
            "VALUES (?, ?, ?, ?)",
            (source, score, total, now),
        )
    return {
        "id": cur.lastrowid,
        "source": source,
        "score": score,
        "total": total,
        "created_at": now,
    }


def create_quiz_attempt(
    db_path: str | Path, source: str | None, questions: list[dict]
) -> dict:
    """Terbitkan paket kuis server-side (P2-04).

    Soal + kunci jawaban (answer_index) disimpan di server. Client hanya
    menerima soal TANPA kunci; skor dihitung deterministik dari kunci.
    Return {"attempt_id", "source", "questions": [tanpa answer_index]}.
    """
    attempt_id = uuid.uuid4().hex
    safe = [
        {
            "question": q.get("question"),
            "options": list(q.get("options") or []),
        }
        for q in questions
    ]
    key = [int(q.get("answer_index", 0)) for q in questions]
    with _conn_learning(db_path) as conn:
        conn.execute(
            "INSERT INTO quiz_attempts (id, source, questions_json, "
            "answer_key_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (attempt_id, source, json.dumps(safe, ensure_ascii=False),
             json.dumps(key, ensure_ascii=False), _now()),
        )
    return {"attempt_id": attempt_id, "source": source, "questions": safe}


def grade_quiz_attempt(
    db_path: str | Path, attempt_id: str, answers: list[int]
) -> dict:
    """Koreksi kuis DETERMINISTIK dari kunci tersimpan (P2-04).

    LLM tidak menentukan skor (skor selalu cocok dengan detail per soal).
    Hasil dicatat ke quiz_scores untuk riwayat/mastery. LLM hanya boleh
    dipakai untuk penjelasan di lapisan di atas fungsi ini.

    Raises:
        ValueError: attempt tidak dikenal / jumlah jawaban tidak cocok.
    """
    with _conn_learning(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM quiz_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
    if row is None:
        raise ValueError("Attempt kuis tidak ditemukan.")
    try:
        questions = json.loads(row["questions_json"] or "[]")
        key = json.loads(row["answer_key_json"] or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("Data attempt kuis rusak.") from exc

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
    save_quiz_score(db_path, row["source"], score, total)
    return {
        "score": score,
        "total": total,
        "correct": [i for i, d in enumerate(details) if d["correct"]],
        "details": details,
    }


def quiz_history(db_path: str | Path, limit: int = 20) -> list[dict]:
    """Riwayat skor kuis terbaru dulu."""
    with _conn_learning(db_path) as conn:
        rows = conn.execute(
            "SELECT id, source, score, total, created_at FROM quiz_scores "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# #5 Flashcards otomatis dari heading
# ----------------------------------------------------------------------
def flashcards(
    store: Any, source: str | None = None, limit: int = 20
) -> list[dict]:
    """Flashcard dari chunk terindeks: satu kartu per heading, tanpa LLM.

    Output [{"heading", "content"}] — content = chunk pertama dari
    heading tersebut. Urut berdasarkan heading (deterministik).
    """
    where = {"source": source} if source else None
    result = store.collection.get(
        where=where, limit=limit * 3, include=["documents", "metadatas"]
    )
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    by_heading: dict[str, str] = {}
    for doc, meta in zip(documents, metadatas, strict=True):
        heading = (meta or {}).get("heading") or "Intro"
        if heading not in by_heading:
            by_heading[heading] = doc
    out = [{"heading": h, "content": c} for h, c in by_heading.items()]
    out.sort(key=lambda e: e["heading"])
    return out[:limit]


def answer_flashcard(
    db_path: str | Path, heading: str, source: str, known: bool
) -> dict:
    """Catat jawaban kartu flashcard (tahu/belum). Return statistik kartu."""
    with _conn_learning(db_path) as conn:
        conn.execute(
            "INSERT INTO flashcard_stats (heading, source, known_count, "
            "unknown_count, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(heading) DO UPDATE SET "
            "known_count = known_count + excluded.known_count, "
            "unknown_count = unknown_count + excluded.unknown_count, "
            "updated_at = excluded.updated_at",
            (heading, source, 1 if known else 0, 0 if known else 1, _now()),
        )
        row = conn.execute(
            "SELECT heading, source, known_count, unknown_count FROM "
            "flashcard_stats WHERE heading = ?",
            (heading,),
        ).fetchone()
    return dict(row)


def flashcard_stats(
    db_path: str | Path, limit: int = 50
) -> list[dict]:
    """Statistik seluruh kartu: tahu vs belum, urut paling sering salah."""
    with _conn_learning(db_path) as conn:
        rows = conn.execute(
            "SELECT heading, source, known_count, unknown_count, updated_at "
            "FROM flashcard_stats ORDER BY unknown_count DESC, known_count "
            "DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# Helper parsing LLM JSON
# ----------------------------------------------------------------------
def _as_int(value: Any, default: int) -> int:
    """Konversi ke int, toleran terhadap string seperti '3/5'."""
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else default


def _strip_code_fence(text: str) -> str:
    """Buang fence markdown ```json ... ``` bila ada."""
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _parse_json_array(text: str) -> list[Any] | None:
    """Parse teks LLM jadi JSON array, toleran fence / teks tambahan."""
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
    """Parse teks LLM jadi JSON object, toleran fence / teks tambahan."""
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
    """Validasi & normalisasi list soal hasil parse JSON."""
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
