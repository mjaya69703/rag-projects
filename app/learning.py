"""Fitur belajar: spaced repetition, weak-spot, progress, quiz, flashcards.

Modul ini punya tabel SQLite sendiri (review_cards, quiz_scores) yang
dibuat idempotent via ``ensure_tables`` / ``_conn_learning`` — tidak
menyentuh schema di app/db.py. Semua timestamp ISO-8601 UTC (sama
dengan konvensi db.py).
"""

from __future__ import annotations

import json
import logging
import random
import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app import db
from app.db import _now

logger = logging.getLogger(__name__)

# Temperature khusus pembuat soal kuis: tinggi supaya tiap generate
# menghasilkan soal yang bervariasi (berbeda dari jawaban chat default).
QUIZ_TEMPERATURE = 0.9

LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_cards (
    card_id       TEXT PRIMARY KEY,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL DEFAULT '',
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

-- Cache flashcard LLM untuk tab Eksplorasi Dokumen: di-generate sekali
-- per sumber lalu dipakai ulang (TTL) supaya tidak memanggil LLM tiap
-- kunjungan halaman.
CREATE TABLE IF NOT EXISTS flashcard_cache (
    source     TEXT PRIMARY KEY,
    cards_json TEXT NOT NULL,
    created_at TEXT NOT NULL
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
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(LEARNING_SCHEMA)
    _migrate_review_cards(conn)
    _migrate_quiz_attempts(conn)
    _migrate_quiz_scores(conn)
    return conn


def _migrate_review_cards(conn: sqlite3.Connection) -> None:
    """Tambah kolom SM-2 (ease_factor, repetitions, answer) ke DB lama (idempotent).

    Schema review_cards pernah berubah beberapa kali; DB lama bisa kekurangan
    kolom apa pun dari definisi penuh (mis. created_at). Migrasi ini menyembuhkan
    sendiri: kolom yang hilang ditambah, sisanya dibiarkan.
    """
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
    if "answer" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN answer TEXT NOT NULL DEFAULT ''"
        )
    if "created_at" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
        )
        conn.execute(
            "UPDATE review_cards SET created_at = ? WHERE created_at = ''",
            (_now(),),
        )
    if "last_reviewed" not in cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN last_reviewed TEXT")
    if "next_due" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN next_due TEXT NOT NULL DEFAULT ''"
        )
    if "interval_days" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 1"
        )
    if "lapses" not in cols:
        conn.execute(
            "ALTER TABLE review_cards ADD COLUMN lapses INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_quiz_attempts(conn: sqlite3.Connection) -> None:
    """Migrasi kolom tabel quiz_attempts (id, questions_json, answer_key_json) (idempotent)."""
    cols = {
        r["name"]
        for r in conn.execute("PRAGMA table_info(quiz_attempts)").fetchall()
    }
    if not cols:
        return
    if "questions_json" not in cols or "total_questions" in cols:
        conn.execute("ALTER TABLE quiz_attempts RENAME TO _quiz_attempts_old")
        conn.execute("""
        CREATE TABLE quiz_attempts (
            id              TEXT PRIMARY KEY,
            source          TEXT,
            questions_json  TEXT NOT NULL,
            answer_key_json TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
        """)
        old_cols = {
            r["name"]
            for r in conn.execute("PRAGMA table_info(_quiz_attempts_old)").fetchall()
        }
        id_col = "id" if "id" in old_cols else "attempt_id" if "attempt_id" in old_cols else None
        if id_col and "questions_json" in old_cols and "answer_key_json" in old_cols:
            conn.execute(
                f"INSERT INTO quiz_attempts (id, source, questions_json, answer_key_json, created_at) "
                f"SELECT {id_col}, source, questions_json, answer_key_json, created_at FROM _quiz_attempts_old"
            )
        conn.execute("DROP TABLE _quiz_attempts_old")


def _migrate_quiz_scores(conn: sqlite3.Connection) -> None:
    """Tautkan skor kuis ke attempt-nya (untuk riwayat + pembahasan ulang)."""
    cols = {
        r["name"]
        for r in conn.execute("PRAGMA table_info(quiz_scores)").fetchall()
    }
    if "attempt_id" not in cols:
        conn.execute("ALTER TABLE quiz_scores ADD COLUMN attempt_id TEXT")


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


def due_cards(db_path: str | Path, source: str | None = None, limit: int = 20) -> list[dict]:
    """Kartu yang sudah waktunya diulang (next_due <= sekarang), urut due."""
    with _conn_learning(db_path) as conn:
        if source:
            rows = conn.execute(
                "SELECT * FROM review_cards WHERE next_due <= ? AND source = ? "
                "ORDER BY next_due ASC LIMIT ?",
                (_now(), source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM review_cards WHERE next_due <= ? "
                "ORDER BY next_due ASC LIMIT ?",
                (_now(), limit),
            ).fetchall()
    return [dict(r) for r in rows]


def list_review_cards(db_path: str | Path, source: str | None = None, limit: int = 100) -> list[dict]:
    """Daftar seluruh kartu flashcard di review_cards."""
    with _conn_learning(db_path) as conn:
        if source:
            rows = conn.execute(
                "SELECT * FROM review_cards WHERE source = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM review_cards ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def create_custom_card(
    db_path: str | Path, question: str, answer: str = "", source: str | None = None
) -> dict:
    """Buat kartu review custom baru."""
    now = _now()
    card_id = uuid.uuid4().hex
    with _conn_learning(db_path) as conn:
        conn.execute(
            "INSERT INTO review_cards (card_id, question, answer, source, created_at, next_due, interval_days, ease_factor, repetitions, lapses) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, 2.5, 0, 0)",
            (card_id, question.strip(), answer.strip(), source, now, now),
        )
        row = conn.execute("SELECT * FROM review_cards WHERE card_id = ?", (card_id,)).fetchone()
    return dict(row)


def delete_review_card(db_path: str | Path, card_id: str) -> bool:
    """Hapus kartu review berdasarkan card_id."""
    with _conn_learning(db_path) as conn:
        cur = conn.execute("DELETE FROM review_cards WHERE card_id = ?", (card_id,))
        return cur.rowcount > 0


def answer_card(
    db_path: str | Path,
    card_id: str,
    rating_or_remembered: int | bool | None = None,
    *,
    remembered: bool | None = None,
) -> dict:
    """Catat hasil review satu kartu dengan algoritma SM-2 multi-level.

    rating:
    1 = Lupa (reset ke 1 hari, repetitions 0, lapses + 1, ease - 0.2)
    2 = Ragu (1 hari, repetitions 1, ease - 0.1)
    3 = Ingat (interval SM-2 standar 1 -> 6 -> interval * ease, ease + 0.1)
    4 = Sangat Paham (interval * ease * 1.3, ease + 0.2)
    """
    if remembered is not None:
        rating_or_remembered = remembered
    if rating_or_remembered is None:
        rating_or_remembered = True

    if isinstance(rating_or_remembered, bool):
        rating = 3 if rating_or_remembered else 1
    else:
        try:
            rating = int(rating_or_remembered)
        except (TypeError, ValueError):
            rating = 3

    now = _now()
    with _conn_learning(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM review_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Kartu tidak ditemukan: {card_id}")

        ease = float(row["ease_factor"] or SM2_INITIAL_EASE)
        reps = int(row["repetitions"] or 0)
        lapses = int(row["lapses"] or 0)
        cur_interval = int(row["interval_days"] or 1)

        if rating == 1:  # Lupa
            reps = 0
            interval = 1
            lapses += 1
            ease = max(SM2_MIN_EASE, ease - 0.2)
        elif rating == 2:  # Ragu
            reps = max(1, reps)
            interval = 1
            ease = max(SM2_MIN_EASE, ease - 0.1)
        elif rating == 3:  # Ingat
            reps += 1
            if reps == 1:
                interval = 1
            elif reps == 2:
                interval = 6
            else:
                interval = round(max(1, cur_interval * ease))
            ease = min(3.5, ease + 0.1)
        elif rating >= 4:  # Sangat Paham
            reps += 1
            if reps == 1:
                interval = 3
            elif reps == 2:
                interval = 8
            else:
                interval = round(max(2, cur_interval * ease * 1.3))
            ease = min(3.5, ease + 0.2)
        else:
            interval = 1

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


def card_stats(db_path: str | Path, source: str | None = None) -> dict:
    """Statistik kartu: total, due hari ini (termasuk yang telat), avg lapses."""
    tomorrow_midnight = (datetime.now(UTC) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    with _conn_learning(db_path) as conn:
        if source:
            total = conn.execute("SELECT COUNT(*) AS n FROM review_cards WHERE source = ?", (source,)).fetchone()["n"]
            due = conn.execute(
                "SELECT COUNT(*) AS n FROM review_cards WHERE next_due < ? AND source = ?",
                (tomorrow_midnight, source),
            ).fetchone()["n"]
            avg = conn.execute("SELECT AVG(lapses) AS a FROM review_cards WHERE source = ?", (source,)).fetchone()["a"]
        else:
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


def _extract_weak_headings(db_path: str | Path | None, source: str | None) -> list[str]:
    """Ekstraksi nama heading/topik yang terindikasi sebagai weak-spot pengguna."""
    if not db_path:
        return []
    headings: list[str] = []
    try:
        ws = weak_spots(db_path, limit=12)
        for item in ws:
            topic = (item.get("topic") or "").strip()
            if not topic:
                continue
            if source:
                if f"({source})" in topic:
                    h = topic.split(f"({source})")[0].strip()
                    if h:
                        headings.append(h)
                elif not topic.startswith("Quiz:"):
                    headings.append(topic)
            else:
                if "(" in topic and ")" in topic:
                    h = topic.split("(")[0].strip()
                    if h:
                        headings.append(h)
                elif not topic.startswith("Quiz:"):
                    headings.append(topic)
    except Exception:
        pass
    return headings


# ----------------------------------------------------------------------
# #4 Quiz generator + skor
# ----------------------------------------------------------------------
def generate_quiz(
    engine: Any,
    source: str | None = None,
    n: int = 5,
    topic: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Buat tepat ``n`` soal pilihan ganda yang mengukur PEMAHAMAN materi.

    Sumber chunk:
    - ``topic`` → cari chunk relevan via hybrid search.
    - tanpa topic → ambil pool chunk lengkap, prioritaskan weak spots jika ada,
      acak urutan chunk, dan diversifikasi per-heading.

    Strategi anti-"1 soal saja" + anti-"soal tolol":
    1. LLM dipanggil PER CHUNK (1 chunk → 1 soal). Lebih reliable daripada
       batch sekaligus — LLM sering "menyusut" output saat konteks panjang.
    2. Prompt mengharuskan soal MENGUKUR PEMAHAMAN (konsep/langkah/alasan/
       istilah spesifik), bukan pertanyaan dangkal "apa yang dibahas".
    3. Retry maks 2× per chunk; jika masih gagal, fallback deterministik
       berbasis ISI chunk: cloze deletion (kalimat rumpang) atau
       ekstraksi kalimat kunci — bukan heading-MCQ.
    4. Total PASTI ``n`` selama materi tersedia.
    """
    weak_headings: list[str] = []
    if db_path and not topic:
        weak_headings = _extract_weak_headings(db_path, source)

    chunks = _collect_quiz_chunks(
        engine.store, source, topic, n, weak_headings=weak_headings
    )
    if not chunks:
        return []

    # Seed acak per-generasi supaya soal yang dihasilkan LLM selalu bervariasi
    # (sudut/fokus detail berbeda) walau chunk yang terpilih sama.
    seed = random.randint(1, 999999)

    questions: list[dict] = []
    used_keys: set[tuple[str, int]] = set()
    used_question_texts: set[str] = set()
    distractors_pool: list[str] = []

    # Kumpulkan kandidat kata/frasa untuk distractor dari SELURUH chunks
    # agar soal fallback punya opsi yang plausible.
    for c in chunks:
        for token in _extract_terms(c.get("text") or ""):
            if token not in distractors_pool:
                distractors_pool.append(token)
    # Acak pool secara dinamis supaya variasi selalu segar
    random.shuffle(distractors_pool)

    for c in chunks:
        if len(questions) >= n:
            break
        key = (c["heading"], len(c.get("text") or ""))
        if key in used_keys and len(chunks) > n:
            continue
        q = _llm_generate_question(engine, c, used_questions=used_question_texts, seed=seed)
        if q is None:
            # Retry dengan prompt lebih sederhana — model lemah sering
            # gagal di prompt panjang.
            q = _llm_generate_question(engine, c, simple=True, used_questions=used_question_texts, seed=seed)
        if q is None:
            q = _content_fallback_question(c, distractors_pool)
        if q is None:
            continue
        if q["question"] in used_question_texts and len(chunks) > n:
            continue
        questions.append(q)
        used_keys.add(key)
        used_question_texts.add(q["question"])

    # Masih kurang (chunk unik terbatas): isi dari chunk duplikat dengan
    # fallback konten agar total persis ``n``.
    if len(questions) < n:
        for c in chunks:
            if len(questions) >= n:
                break
            q = _content_fallback_question(c, distractors_pool)
            if q is None:
                continue
            questions.append(q)

    return questions[:n]


def _collect_quiz_chunks(
    store: Any,
    source: str | None,
    topic: str | None,
    n: int,
    weak_headings: list[str] | None = None,
) -> list[dict]:
    """Kumpulkan chunk untuk kuis dengan pengacakan, diversifikasi heading, dan prioritas weak-spot.

    Strategi:
    1. Mengambil pool chunk yang luas dari database (bukan cuma n teratas).
    2. Bila ada weak_headings (topik yang sering salah), chunk dari heading tersebut diprioritaskan.
    3. Acak (shuffle) urutan heading dan chunk sehingga kuis selalu segar dan tersebar merata.
    4. Mengutamakan 1 chunk per heading berbeda sebelum mengulang heading yang sama.
    """
    where = {"source": source} if source else None
    target = max(n * 2, 12)
    raw_pool: list[dict] = []

    if topic:
        results = store.search(topic, top_k=max(target * 2, 20), where=where)
        for r in results:
            meta = r.get("metadata") or {}
            heading = (meta.get("heading") or "Intro").strip()
            raw_pool.append({"text": r.get("text", ""), "heading": heading})
    else:
        result = store.collection.get(
            where=where, limit=500, include=["documents", "metadatas"]
        )
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        for doc, meta in zip(docs, metas, strict=False):
            heading = ((meta or {}).get("heading") or "Intro").strip()
            raw_pool.append({"text": doc, "heading": heading})

    if not raw_pool:
        return []

    # Kelompokkan chunk per heading
    by_heading: dict[str, list[dict]] = {}
    for c in raw_pool:
        h = c["heading"]
        by_heading.setdefault(h, []).append(c)

    # Acak chunk di dalam setiap heading
    for h in by_heading:
        random.shuffle(by_heading[h])

    chosen: list[dict] = []
    seen_texts: set[str] = set()

    # Prioritaskan weak spots jika tersedia (maksimal n // 2 atau jumlah weak_headings)
    if weak_headings:
        norm_weak = {w.lower() for w in weak_headings}
        weak_h_keys = [
            h for h in by_heading
            if h.lower() in norm_weak or any(w in h.lower() for w in norm_weak)
        ]
        random.shuffle(weak_h_keys)
        for h in weak_h_keys:
            if len(chosen) >= max(1, n // 2):
                break
            if by_heading[h]:
                c = by_heading[h].pop()
                if c["text"] not in seen_texts:
                    chosen.append(c)
                    seen_texts.add(c["text"])

    # Ambil heading unik secara acak untuk sisa target
    headings = list(by_heading.keys())
    random.shuffle(headings)

    # Round-robin pengambilan 1 chunk per heading unik
    while len(chosen) < target:
        added_in_round = False
        for h in headings:
            if len(chosen) >= target:
                break
            if by_heading[h]:
                c = by_heading[h].pop()
                if c["text"] not in seen_texts:
                    chosen.append(c)
                    seen_texts.add(c["text"])
                    added_in_round = True
        if not added_in_round:
            break

    # Jika pool chunk unik sangat sedikit, duplikasi bila perlu hingga minimal target atau len(raw_pool)
    if len(chosen) < target and raw_pool:
        shuffled_raw = list(raw_pool)
        random.shuffle(shuffled_raw)
        for c in shuffled_raw:
            if len(chosen) >= target:
                break
            chosen.append(c)

    return chosen


def _clean_question_text(question: str) -> str:
    """Bersihkan prefix meta/judul yang sering ditambahkan model LLM."""
    q = question.strip()
    patterns = [
        r"^Bagian\s+['\"].*?['\"]\s*[-—:]\s*",
        r"^Berdasarkan\s+Bagian\s+['\"].*?['\"]\s*[,—:]\s*",
        r"^Berdasarkan\s+cuplikan\s+materi\s*[,—:]\s*",
        r"^Berdasarkan\s+teks\s+di\s+atas\s*[,—:]\s*",
    ]
    for pat in patterns:
        q = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
    return q


def _llm_generate_question(
    engine: Any,
    chunk: dict,
    simple: bool = False,
    used_questions: set[str] | None = None,
    seed: int | None = None,
) -> dict | None:
    """Minta LLM SATU soal pilihan ganda berbasis pemahaman mendalam dari chunk."""
    heading = chunk.get("heading") or "Materi"
    text = (chunk.get("text") or "").strip()
    if not text or len(text) < 40:
        return None
    snippet = text[:1500]

    variation_note = (
        "VARIASI SOAL: Gunakan benih acak (seed) berikut untuk memilih sudut yang "
        f"berbeda dari teks: {seed if seed is not None else random.randint(1, 999999)}. "
        "Jika potongan teks yang sama di-generate lagi, pilih detail, konsep, atau "
        "implikasi LAIN yang belum ditanyakan. Jangan mengulang pertanyaan yang sama."
    )

    base_prompt = (
        f"Bagian: {heading}\n\n"
        "Anda adalah AI pembuat soal ujian sertifikasi teknis dan pemahaman konsep (High Quality HOTS Quiz Maker).\n\n"
        "TUGAS: Buat TEPAT 1 (SATU) soal pilihan ganda yang menguji PEMAHAMAN KONSEPTUAL, FUNGSI TEKNIS, ALASAN/SEBAB-AKIBAT, atau CARA KERJA dari teks materi berikut:\n\n"
        "=== TEKS MATERI ===\n"
        f"{snippet}\n"
        "===================\n\n"
        "CONTOH SOAL YANG BAIK:\n"
        "- 'Apa fungsi utama dari konfigurasi SSL mode Full (Strict)?'\n"
        "- 'Mengapa port 8443 harus dibuka saat mengakses dashboard?'\n"
        "- 'Bagaimana dampak dari kesalahan konfigurasi DNS A record terhadap akses website?'\n\n"
        "CONTOH SOAL YANG DILARANG KERAS:\n"
        "- JANGAN BUAT: 'Bagian ini membahas apa?'\n"
        "- JANGAN BUAT: 'Di halaman ini dibahas tentang apa?'\n"
        "- JANGAN BUAT: 'Apa topik utama teks di atas?'\n\n"
        "ATURAN PEMBUATAN:\n"
        "1. Soal WAJIB fokus pada esensi materi teknis (fungsi, cara kerja, alasan teknis, atau implikasi sistem).\n"
        "2. 4 Opsi Jawaban (A/B/C/D): 1 jawaban benar dan 3 pengecoh yang substantif dan masuk akal.\n"
        "3. Format Output HANYA JSON object tanpa teks lain:\n"
        '{"question": "Pertanyaan spesifik mengenai konsep/langkah teknis...", "options": ["Opsi A", "Opsi B", "Opsi C", "Opsi D"], "answer_index": 0}\n\n'
        f"4. {variation_note}\n\n"
        "JSON:"
    )

    retry_prompt = (
        f"Bagian: {heading}\n\n"
        f"Dari materi teknis berikut:\n\n{snippet}\n\n"
        "Buat 1 soal pilihan ganda berbobot teknis yang menguji detail konsep atau mekanisme kerja. "
        "DILARANG membuat pertanyaan meta seperti 'membahas apa' atau 'tentang apa'.\n"
        f"{variation_note}\n"
        "Jawab HANYA JSON:\n"
        '{"question": "Pertanyaan teknis spesifik...", "options": ["Opsi A", "Opsi B", "Opsi C", "Opsi D"], "answer_index": 0}'
    )

    prompts_to_try = [base_prompt, retry_prompt] if not simple else [retry_prompt]
    for p in prompts_to_try:
        try:
            response = engine.llm.chat(
                [{"role": "user", "content": p}],
                max_tokens=min(1024, max(512, len(snippet) // 3)),
                temperature=QUIZ_TEMPERATURE,
            )
            raw = response.text.strip()
            cleaned = _strip_code_fence(raw)
            obj = _parse_json_object(cleaned)
            if obj:
                normalized = _normalize_question_dict(obj)
                if normalized:
                    normalized["question"] = _clean_question_text(normalized["question"])
                    if used_questions is None or normalized["question"] not in used_questions:
                        return _shuffle_question_options(normalized)
            parsed = _parse_questions(cleaned)
            if parsed:
                for item in parsed:
                    normalized = _normalize_question_dict(item)
                    if normalized:
                        normalized["question"] = _clean_question_text(normalized["question"])
                        if used_questions is None or normalized["question"] not in used_questions:
                            return _shuffle_question_options(normalized)
                for item in parsed:
                    normalized = _normalize_question_dict(item)
                    if normalized:
                        normalized["question"] = _clean_question_text(normalized["question"])
                        return _shuffle_question_options(normalized)
        except Exception as exc:
            logger.warning("quiz LLM exception untuk heading=%r: %s", heading, exc)

    return None


def _shuffle_question_options(q: dict) -> dict:
    """Acak posisi opsi jawaban dan perbaiki ``answer_index`` mengikuti.

    Menjamin posisi huruf jawaban (A/B/C/D) selalu beda tiap generate walau
    teks pertanyaannya mirip.
    """
    options = q.get("options")
    if not isinstance(options, list) or len(options) < 2:
        return q
    correct = options[q.get("answer_index", 0)]
    idx = list(range(len(options)))
    random.shuffle(idx)
    shuffled = [options[i] for i in idx]
    q["options"] = shuffled
    q["answer_index"] = shuffled.index(correct)
    return q


def _extract_terms(text: str, limit: int = 40) -> list[str]:
    """Ambil istilah/kata kunci dari teks untuk kandidat distractor.

    Filter: panjang >= 5 karakter, alfanumerik, huruf besar-kecil,
    menghindari stopword umum Indonesia & Inggris sederhana.
    """
    if not text:
        return []
    stop = {
        "adalah", "sebuah", "dengan", "untuk", "dari", "yang", "pada",
        "dalam", "akan", "telah", "dapat", "atau", "juga", "oleh",
        "this", "that", "with", "from", "yang", "akan", "dengan",
        "the", "and", "dapat", "sehingga", "karena", "antara", "yaitu",
        "bagian", "membahas", "topik", "lain", "tidak", "tahu", "adanya",
    }
    tokens = re.findall(r"\b[A-Za-z][A-Za-z\-]{4,}\b", text)
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t.lower() in stop:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def _content_fallback_question(chunk: dict, distractors_pool: list[str]) -> dict | None:
    """Soal fallback jika LLM offline: evaluasi pernyataan teknis substantif."""
    text = (chunk.get("text") or "").strip()
    heading = chunk.get("heading") or "Materi"
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
        if len(s.strip()) >= 50
    ]
    if not sentences:
        return None
    target_sentence = random.choice(sentences)
    if len(target_sentence) > 280:
        target_sentence = target_sentence[:280].rsplit(" ", 1)[0] + "."

    # Evaluasi Pernyataan Teknis (Statement Evaluation)
    true_stmt = target_sentence
    false_pool = [
        "Tidak didukung oleh konfigurasi sistem pada arsitektur ini.",
        "Hanya berlaku pada mode pengembangan dan dilarang di lingkungan produksi.",
        "Prinsip kerjanya bertolak belakang dengan konfigurasi jaringan standar.",
        "Konfigurasi ini memerlukan izin otorisasi khusus sebelum dapat diterapkan.",
    ]
    random.shuffle(false_pool)
    options = [true_stmt] + false_pool[:3]
    correct_idx = random.randint(0, len(options) - 1)
    options[0], options[correct_idx] = options[correct_idx], options[0]
    return {
        "question": f"Manakah pernyataan teknis berikut yang PALING TEPAT mengenai {heading}?",
        "options": options,
        "answer_index": correct_idx,
    }


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
    db_path: str | Path, source: str | None, score: int, total: int,
    attempt_id: str | None = None,
) -> dict:
    """Simpan hasil kuis ke tabel quiz_scores. Return baris yang tersimpan."""
    now = _now()
    with _conn_learning(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO quiz_scores (source, score, total, attempt_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (source, score, total, attempt_id, now),
        )
    return {
        "id": cur.lastrowid,
        "source": source,
        "score": score,
        "total": total,
        "attempt_id": attempt_id,
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
    save_quiz_score(db_path, row["source"], score, total, attempt_id=attempt_id)
    return {
        "score": score,
        "total": total,
        "correct": [i for i, d in enumerate(details) if d["correct"]],
        "details": details,
    }


def quiz_attempt_detail(
    db_path: str | Path, attempt_id: str
) -> dict | None:
    """Detail satu attempt kuis: soal + kunci jawaban + skor (bila sudah dikerjakan).

    Dipakai untuk pembahasan ulang kuis dari riwayat.
    """
    with _conn_learning(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM quiz_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        if row is None:
            return None
        score_row = conn.execute(
            "SELECT score, total FROM quiz_scores "
            "WHERE attempt_id = ? ORDER BY id DESC LIMIT 1",
            (attempt_id,),
        ).fetchone()
    try:
        questions = json.loads(row["questions_json"] or "[]")
        key = json.loads(row["answer_key_json"] or "[]")
    except json.JSONDecodeError:
        return None

    out_questions: list[dict] = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        out_questions.append(
            {
                "question": q.get("question", ""),
                "options": list(q.get("options") or []),
                "correct_index": key[i] if i < len(key) else -1,
            }
        )
    return {
        "attempt_id": row["id"],
        "source": row["source"],
        "created_at": row["created_at"],
        "score": score_row["score"] if score_row else None,
        "total": score_row["total"] if score_row else None,
        "questions": out_questions,
    }


def explain_quiz_questions(
    engine: Any,
    db_path: str | Path,
    attempt_id: str,
    answers: list[int],
) -> list[str]:
    """Pembahasan per soal via LLM — opsional, tidak memengaruhi skor.

    Satu panggilan LLM batch untuk semua soal. Bila LLM tak tersedia /
    gagal / respons tidak valid, kembalikan [] agar UI menampilkan hasil
    tanpa pembahasan (skor tetap deterministik).
    """
    try:
        with _conn_learning(db_path) as conn:
            row = conn.execute(
                "SELECT questions_json, answer_key_json FROM quiz_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
        if not row:
            return []
        questions = json.loads(row["questions_json"] or "[]")
        key = json.loads(row["answer_key_json"] or "[]")
    except Exception:
        return []
    if not questions:
        return []

    lines: list[str] = []
    for i, q in enumerate(questions[:25]):
        if not isinstance(q, dict):
            continue
        options = q.get("options") or []
        correct = key[i] if i < len(key) else None
        correct_text = (
            options[correct]
            if isinstance(correct, int) and 0 <= correct < len(options)
            else "?"
        )
        user_choice = answers[i] if i < len(answers) else None
        user_text = (
            options[user_choice]
            if isinstance(user_choice, int) and 0 <= user_choice < len(options)
            else "tidak dijawab"
        )
        verdict = "benar" if user_choice == correct else "salah"
        lines.append(
            f"[Soal {i+1}] {q.get('question', '')}\n"
            f"Pilihan: {', '.join(str(o) for o in options)}\n"
            f"Jawaban benar: {correct_text}\n"
            f"Jawaban user: {user_text} ({verdict})"
        )
    if not lines:
        return []

    prompt = (
        "Anda adalah tutor AI ahli. Untuk setiap soal di bawah, tuliskan PEMBAHASAN "
        "singkat (1-3 kalimat) mengapa jawaban benar itu benar. Bila jawaban user "
        "salah, sebutkan juga mengapa pilihan user kurang tepat.\n\n"
        "Keluarkan HANYA JSON array of strings (satu elemen per soal) tanpa teks lain:\n"
        '["pembahasan soal 1", "pembahasan soal 2", ...]\n\n'
        "SOAL-SOAL:\n"
        + "\n\n".join(lines)
    )
    from app.llm_client import LLMError

    try:
        res = engine.llm.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=min(4096, max(1024, len(lines) * 160)),
        )
    except LLMError:
        return []
    except Exception:
        logger.exception("pembahasan kuis gagal, lanjut tanpa pembahasan")
        return []

    data = _parse_json_array(_strip_code_fence(res.text))
    if not isinstance(data, list):
        return []
    out = [str(x).strip() for x in data if isinstance(x, str) and x.strip()]
    return out[: len(questions)]


def quiz_history(
    db_path: str | Path, limit: int = 20, offset: int = 0
) -> list[dict]:
    """Riwayat skor kuis terbaru dulu (dengan pagination)."""
    with _conn_learning(db_path) as conn:
        rows = conn.execute(
            "SELECT id, source, score, total, attempt_id, created_at "
            "FROM quiz_scores ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, max(0, offset)),
        ).fetchall()
    return [dict(r) for r in rows]


def count_quiz_history(db_path: str | Path) -> int:
    with _conn_learning(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM quiz_scores").fetchone()
    return int(row["c"])


# ----------------------------------------------------------------------
# #5 Flashcards — eksplorasi dokumen: LLM menentukan konten (logis)
# ----------------------------------------------------------------------
FLASHCARD_CACHE_TTL_SEC = 6 * 60 * 60  # regenerasi LLM maks 1x / 6 jam / sumber


def _chunk_flashcards(
    store: Any, source: str | None = None, limit: int = 20
) -> list[dict]:
    """Fallback tanpa LLM: satu kartu per heading / segmen unik."""
    where = {"source": source} if source else None
    result = store.collection.get(
        where=where, limit=limit * 4, include=["documents", "metadatas"]
    )
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    by_heading: dict[str, str] = {}
    for idx, (doc, meta) in enumerate(zip(documents, metadatas, strict=True)):
        m = meta or {}
        heading = m.get("heading")
        page = m.get("page")
        src = m.get("source", source or "Dokumen")

        if heading and heading.lower() not in {"intro", "pengenalan", "none"}:
            card_title = heading
        elif page is not None and page > 0:
            card_title = f"{src} (Halaman {page})"
        else:
            first_line = doc.strip().split("\n")[0][:80]
            card_title = first_line if first_line else f"{src} - Bagian {idx + 1}"

        if card_title not in by_heading:
            by_heading[card_title] = doc.strip()

    out = [{"heading": h, "content": c} for h, c in by_heading.items()]
    out.sort(key=lambda e: e["heading"])
    return out[:limit]


def _llm_flashcards(
    engine: Any, store: Any, source: str | None = None, limit: int = 20
) -> list[dict]:
    """Flashcard Q&A logis hasil penalaran LLM: front = konsep/pertanyaan,
    back = penjelasan ringkas. Bukan sekadar potongan chunk/heading."""
    where = {"source": source} if source else None
    result = store.collection.get(
        where=where,
        limit=max(limit * 3, 20),
        include=["documents", "metadatas"],
    )
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    if not documents:
        return []

    sections: list[str] = []
    for idx, (doc, meta) in enumerate(zip(documents, metadatas, strict=True)):
        m = meta or {}
        src = m.get("source", source or "Dokumen")
        page = m.get("page", "?")
        heading = m.get("heading", "Intro")
        sections.append(
            f"[BAGIAN {idx+1}] Sumber={src}; Hal={page}; Judul={heading}\n{doc[:1500]}"
        )
    context = "\n\n".join(sections)[:24000]

    prompt = (
        f"Anda adalah tutor AI ahli. Buatkan tepat {limit} flashcard belajar aktif "
        "(Active Recall) yang LOGIS dan bernilai tinggi dari materi dokumen di bawah ini.\n"
        "Pikiran Andalah yang menentukan konten tiap kartu — jangan sekadar menyalin "
        "potongan teks mentah atau judul heading.\n\n"
        "Setiap kartu HARUS berupa:\n"
        "1. 'heading': Pertanyaan atau konsep kunci yang jelas, spesifik, dan menguji pemahaman esensial.\n"
        "2. 'content': Jawaban/penjelasan ringkas, terstruktur, mudah dihafal (poin-poin/definisi).\n"
        "3. 'source': Nama file dokumen sumber.\n\n"
        "Hindari kartu dangkal atau duplikat; prioritaskan konsep yang benar-benar penting.\n"
        "Keluarkan HANYA JSON array tanpa teks lain:\n"
        '[{"heading": "...", "content": "...", "source": "..."}]\n\n'
        f"DOKUMEN MATERI:\n{context}"
    )
    from app.llm_client import LLMError

    try:
        res = engine.llm.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=min(4096, max(1024, limit * 220)),
        )
    except Exception as exc:
        if isinstance(exc, LLMError):
            raise
        raise LLMError(f"Gagal generate flashcard via AI: {exc}") from exc

    cards_data = _parse_json_array(_strip_code_fence(res.text))
    if not cards_data:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for c in cards_data:
        if not isinstance(c, dict):
            continue
        heading = str(
            c.get("heading") or c.get("question") or c.get("front") or ""
        ).strip()
        content = str(
            c.get("content") or c.get("answer") or c.get("back") or ""
        ).strip()
        if not heading or not content:
            continue
        norm = heading.lower().strip()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(
            {
                "heading": heading,
                "content": content,
                "source": str(c.get("source") or source or "").strip(),
            }
        )
        if len(out) >= limit:
            break
    return out


def _cache_get_flashcards(
    db_path: str | Path | None, source: str | None
) -> list[dict] | None:
    """Ambil flashcard LLM dari cache bila masih segar."""
    if not db_path:
        return None
    try:
        with _conn_learning(db_path) as conn:
            row = conn.execute(
                "SELECT cards_json, created_at FROM flashcard_cache WHERE source = ?",
                (source or "",),
            ).fetchone()
        if not row:
            return None
        age = datetime.now(UTC) - datetime.fromisoformat(row["created_at"])
        if age.total_seconds() > FLASHCARD_CACHE_TTL_SEC:
            return None
        data = json.loads(row["cards_json"])
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _cache_put_flashcards(
    db_path: str | Path | None, source: str | None, cards: list[dict]
) -> None:
    if not db_path:
        return
    try:
        with _conn_learning(db_path) as conn:
            conn.execute(
                "INSERT INTO flashcard_cache (source, cards_json, created_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(source) DO UPDATE SET cards_json = excluded.cards_json, "
                "created_at = excluded.created_at",
                (source or "", json.dumps(cards, ensure_ascii=False), _now()),
            )
    except Exception:
        logger.exception("gagal menulis cache flashcard")


def flashcards(
    store: Any,
    source: str | None = None,
    limit: int = 20,
    engine: Any = None,
    db_path: str | Path | None = None,
    force: bool = False,
) -> list[dict]:
    """Flashcard untuk tab Eksplorasi Dokumen.

    Prioritas: kartu Q&A logis hasil penalaran LLM (di-cache per sumber,
    TTL 6 jam) → fallback satu kartu per heading/chunk bila LLM tidak
    tersedia, gagal, atau responsnya tidak valid.
    """
    if engine is not None:
        if not force:
            cached = _cache_get_flashcards(db_path, source)
            if cached is not None:
                return cached[:limit]
        try:
            cards = _llm_flashcards(engine, store, source=source, limit=limit)
            if cards:
                _cache_put_flashcards(db_path, source, cards)
                return cards[:limit]
        except Exception:
            logger.exception("flashcards LLM gagal, fallback ke chunk")
    return _chunk_flashcards(store, source=source, limit=limit)


# ----------------------------------------------------------------------
# #6 Mindmap & ringkasan dokumen (dipakai endpoint /learning/*)
# ----------------------------------------------------------------------
def mindmap_tree(store: Any, source: str | None = None) -> dict:
    """Tree mindmap dari heading dokumen terindeks.

    Struktur: root (Knowledge Base / nama sumber) → per source → per
    heading. Tanpa LLM — murni dari metadata chunk.
    """
    where = {"source": source} if source else None
    result = store.collection.get(where=where, include=["metadatas"])
    metas = result.get("metadatas") or []
    if not metas:
        return {"name": source or "Knowledge Base", "children": []}

    root = {"name": source or "Knowledge Base", "children": []}
    buckets: dict[str, list] = {}
    for m in metas:
        meta = m or {}
        src = meta.get("source", "General")
        heading = (meta.get("heading") or "").strip() or "Intro"
        buckets.setdefault(f"{src} > {heading}", [])

    for key in buckets:
        parts = key.split(" > ")
        current = root
        for part in parts:
            child = next(
                (c for c in current["children"] if c["name"] == part), None
            )
            if child is None:
                child = {"name": part, "children": []}
                current["children"].append(child)
            current = child
    return root


def document_summary(
    engine: Any, source: str, max_tokens: int = 500
) -> str:
    """Ringkasan otomatis satu dokumen via LLM dari cuplikan chunk teratas."""
    result = engine.store.collection.get(
        where={"source": source}, limit=10, include=["documents"]
    )
    docs = result.get("documents") or []
    if not docs:
        return "Dokumen tidak ditemukan atau belum terindeks."
    material = "\n\n".join(d[:600] for d in docs)
    prompt = (
        f"Buat ringkasan komprehensif dan terstruktur untuk dokumen '{source}' "
        "berdasarkan cuplikan berikut dalam bahasa Indonesia "
        f"(maksimal 3 paragraf):\n\n{material}"
    )
    try:
        res = engine.llm.chat(
            [{"role": "user", "content": prompt}], max_tokens=max_tokens
        )
        return res.text.strip()
    except Exception:
        logger.exception("ringkasan dokumen gagal: %s", source)
        return "Gagal menghasilkan ringkasan dokumen."


def generate_flashcards(
    engine: Any, source: str | None = None, n: int = 5
) -> list[dict]:
    """Ekstrak flashcards Active Recall berkualitas tinggi menggunakan LLM."""
    n = max(1, min(n, 25))
    where = {"source": source} if source else None
    result = engine.store.collection.get(
        where=where,
        limit=max(n * 3, 20),
        include=["documents", "metadatas"],
    )
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    if not documents:
        return []

    sections: list[str] = []
    for idx, (doc, meta) in enumerate(zip(documents, metadatas, strict=True)):
        m = meta or {}
        src = m.get("source", source or "Dokumen")
        page = m.get("page", "?")
        heading = m.get("heading", "Intro")
        sections.append(f"[BAGIAN {idx+1}] Sumber={src}; Hal={page}; Judul={heading}\n{doc[:2000]}")
    context = "\n\n".join(sections)[:24000]

    prompt = (
        f"Anda adalah asisten tutor AI ahli. Buatkan tepat {n} buah flashcard belajar aktif (Active Recall) "
        "dari materi dokumen di bawah ini.\n\n"
        "Setiap flashcard HARUS memiliki:\n"
        "1. 'front': Pertanyaan atau konsep kunci yang jelas, fokus, dan menguji pemahaman konsep esensial.\n"
        "2. 'back': Jawaban yang terstruktur, padat, mudah dihafal (bisa berbentuk poin-poin penting / ringkasan definisi).\n"
        "3. 'source': Nama file dokumen sumber.\n"
        "4. 'page': Nomor halaman (angka integer) atau null jika tidak ada.\n\n"
        "Keluarkan HANYA JSON array dengan format berikut tanpa teks lain:\n"
        '[{"front": "...", "back": "...", "source": "...", "page": 1}]\n\n'
        f"DOKUMEN MATERI:\n{context}"
    )
    try:
        from app.llm_client import LLMError
        res = engine.llm.chat([{"role": "user", "content": prompt}], max_tokens=min(4096, max(1024, n * 300)))
        raw = _strip_code_fence(res.text)
        try:
            cards_data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                cards_data = json.loads(match.group(0))
            else:
                cards_data = []
        if isinstance(cards_data, dict):
            cards_data = cards_data.get("cards", cards_data.get("flashcards", []))
        if not isinstance(cards_data, list):
            return []

        out: list[dict] = []
        for c in cards_data:
            if not isinstance(c, dict):
                continue
            front = str(c.get("front") or c.get("question") or "").strip()
            back = str(c.get("back") or c.get("answer") or c.get("content") or "").strip()
            if not front or not back:
                continue
            card_source = str(c.get("source") or source or "").strip()
            page = c.get("page")
            try:
                page = int(page) if page is not None else None
            except (ValueError, TypeError):
                page = None
            out.append({
                "front": front,
                "back": back,
                "source": card_source,
                "page": page,
            })
            if len(out) >= n:
                break
        return out
    except Exception as exc:
        raise LLMError(f"Gagal generate flashcards via AI: {exc}") from exc


def save_flashcards_to_deck(
    db_path: str | Path, cards: list[dict], dedupe: bool = False
) -> list[dict]:
    """Simpan daftar kartu flashcard (hasil AI/manual) ke review_cards.

    ``dedupe=True`` melewati kartu yang pertanyaannya sudah ada (case/tab
    tidak sensitif) — dipakai konversi jawaban kuis yang salah.
    """
    now = _now()
    saved: list[dict] = []
    existing: set[str] = set()
    with _conn_learning(db_path) as conn:
        if dedupe:
            existing = {
                row["question"].strip().lower()
                for row in conn.execute(
                    "SELECT question FROM review_cards"
                ).fetchall()
            }
        for c in cards:
            card_id = uuid.uuid4().hex
            question = c.get("front") or c.get("question") or ""
            answer = c.get("back") or c.get("answer") or ""
            src = c.get("source") or None
            if not question:
                continue
            norm = question.strip().lower()
            if dedupe and norm in existing:
                continue
            existing.add(norm)
            conn.execute(
                "INSERT INTO review_cards (card_id, question, answer, source, created_at, next_due, interval_days, ease_factor, repetitions, lapses) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, 2.5, 0, 0)",
                (card_id, question, answer, src, now, now),
            )
            saved.append({
                "card_id": card_id,
                "question": question,
                "answer": answer,
                "source": src,
                "next_due": now,
                "interval_days": 1,
                "ease_factor": 2.5,
                "repetitions": 0,
                "lapses": 0,
            })
    return saved


def save_wrong_answers_to_deck(
    db_path: str | Path, attempt_id: str, details: list[dict]
) -> list[dict]:
    """Ubah soal kuis yang dijawab SALAH menjadi kartu review SM-2 (dedupe).

    Menutup loop belajar: salah di kuis → langsung masuk antrean repetisi.
    Return daftar kartu yang berhasil disimpan.
    """
    attempt = quiz_attempt_detail(db_path, attempt_id)
    if not attempt:
        return []
    by_question = {q["question"]: q for q in attempt["questions"]}
    cards: list[dict] = []
    for d in details:
        if d.get("correct"):
            continue
        q = by_question.get(d.get("question", ""))
        if not q:
            continue
        options = q.get("options") or []
        ci = q.get("correct_index", -1)
        answer = options[ci] if 0 <= ci < len(options) else ""
        cards.append(
            {
                "front": q["question"],
                "back": answer,
                "source": attempt["source"],
            }
        )
    if not cards:
        return []
    return save_flashcards_to_deck(db_path, cards, dedupe=True)


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


def learning_recommendations(db_path: str | Path) -> dict:
    """Buat rekomendasi aksi belajar cerdas berdasarkan data riwayat, weak-spots, dan retensi."""
    spots = weak_spots(db_path, limit=5)
    c_stats = card_stats(db_path)
    m_stats = mastery_stats(db_path)

    recs = []
    if c_stats.get("due_today", 0) > 0:
        recs.append({
            "type": "flashcards",
            "title": f"Ada {c_stats['due_today']} Kartu Due Hari Ini",
            "description": "Jaga ingatan jangka panjang Anda dengan mengulang kartu yang telah jatuh tempo.",
            "action": "study_due",
            "priority": "high",
        })

    for ws in spots[:3]:
        recs.append({
            "type": "weak_spot",
            "title": f"Perkuat Pemahaman: {ws['topic']}",
            "description": f"Topik ini sering ditanyakan atau salah (Skor kelemahan: {ws['score']}). Disarankan latihan kuis remedial.",
            "action": "remedy_quiz",
            "topic": ws["topic"],
            "priority": "medium",
        })

    if not recs:
        recs.append({
            "type": "general",
            "title": "Performa Belajar Sangat Baik!",
            "description": "Tidak ada kartu yang tertunda dan pemahaman materi Anda solid. Lanjutkan dengan mengeksplorasi dokumen baru atau membuat kuis evaluasi.",
            "action": "new_quiz",
            "priority": "low",
        })

    return {
        "status": "ok",
        "card_stats": c_stats,
        "recommendations": recs,
        "mastery_summary": m_stats,
        "weak_spots": spots,
    }


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


def _is_shallow_question(question: str) -> bool:
    """Deteksi pertanyaan meta/dangkal yang tidak menguji pemahaman konsep nyata.

    Menolak pertanyaan seperti 'Bagian X membahas apa?', 'Di halaman ini bahas apa?',
    'Apa topik utama...', 'Teks ini berisi tentang apa?', dan varian dangkal lainnya.
    """
    q_lower = question.lower().strip()
    shallow_phrases = [
        "membahas apa",
        "bahas apa",
        "membahas tentang apa",
        "membahas topik apa",
        "apa yang dibahas",
        "apa yang dipelajari",
        "apa yang dijelaskan",
        "apa yang diterangkan",
        "topik apa yang",
        "tentang apa",
        "berisi tentang apa",
        "menceritakan tentang apa",
        "fokus utama dari",
        "apa isi dari",
        "apa tujuan dari teks",
        "apa pesan dari",
        "apa tema dari",
        "rangkuman dari",
        "ringkasan dari",
        "judul dari teks",
        "cuplikan",
        "di halaman",
        "pada halaman",
        "dihalaman",
        "padahalaman",
        "halaman berapa",
        "halaman ke",
        "dalam halaman",
    ]
    if any(p in q_lower for p in shallow_phrases):
        return True

    # Pertanyaan yang menanyakan isi bagian/halaman/teks secara meta
    if any(q_lower.startswith(prefix) for prefix in [
        "bagian '", 'bagian "', "bagian ",
        "pada bagian", "di bagian", "dalam bagian",
        "halaman ", "pada halaman", "di halaman", "dihalaman",
        "teks di atas", "dokumen di atas", "bacaan di atas", "paragraf di atas"
    ]):
        if any(w in q_lower for w in [
            "membahas", "bahas", "topik", "tentang", "fokus",
            "menjelaskan apa", "apa isi", "mengenai apa", "tujuan", "membicarakan"
        ]):
            return True

    return False


def _normalize_question_dict(obj: dict) -> dict | None:
    """Normalisasi dict hasil parse LLM jadi shape soal quiz.

    Menerima variasi key umum: ``answer_index``/``answer``/``correct``/
    ``correct_index``/``correct_answer_index``; ``options``/``choices``/
    ``answers``/``alternatives``. Lewati jika field esensial hilang
    atau jika pertanyaan terdeteksi dangkal/meta.
    """
    question = (
        obj.get("question")
        or obj.get("q")
        or obj.get("pertanyaan")
        or obj.get("soal")
    )
    options = (
        obj.get("options")
        or obj.get("choices")
        or obj.get("answers")
        or obj.get("alternatives")
        or obj.get("opsi")
    )
    if not isinstance(question, str) or not question.strip():
        return None
    clean_q = question.strip()
    if _is_shallow_question(clean_q):
        logger.warning("quiz LLM: soal ditolak karena terlalu dangkal/meta: %r", clean_q)
        return None
    if not isinstance(options, list):
        return None
    clean_options = [str(o).strip() for o in options if str(o).strip()][:4]
    if len(clean_options) < 2:
        return None
    raw_answer = (
        obj.get("answer_index")
        if "answer_index" in obj
        else (
            obj.get("correct_index")
            or obj.get("answer")
            or obj.get("correct")
            or obj.get("correct_answer")
            or obj.get("correct_answer_index")
            or obj.get("jawaban_benar")
            or 0
        )
    )
    answer_index = _as_int(raw_answer, 0)
    answer_index = max(0, min(answer_index, len(clean_options) - 1))
    return {
        "question": clean_q,
        "options": clean_options,
        "answer_index": answer_index,
    }


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
    """Parse teks LLM jadi JSON object, toleran fence / teks tambahan.

    Pakai regex NON-GREEDY agar objek dalam yang disisipkan di teks
    panjang (penjelasan tambahan LLM) tidak bikin match greedy menelan
    terlalu banyak karakter dan menghasilkan JSON invalid.
    """
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
    # Cari object JSON pertama yang balanced (handle brace seimbang).
    for start in (m.start() for m in re.finditer(r"\{", cleaned)):
        depth = 0
        end = -1
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > 0:
            try:
                data = json.loads(cleaned[start:end])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
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
