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

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    ip          TEXT NOT NULL DEFAULT '',
    status      INTEGER NOT NULL,
    duration_ms REAL NOT NULL DEFAULT 0
);

-- Document registry: source of truth untuk lifecycle file/index.
-- status: queued | processing | ready | error
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
"""


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _conn(db_path) as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------------
# Glossary
# ----------------------------------------------------------------------
def list_glossary(
    db_path: str | Path,
    search: str = "",
    source: str | None = None,
    verified: bool | None = None,
    limit: int = 100,
) -> list[dict]:
    """Daftar istilah dengan pencarian term/definisi yang case-insensitive."""
    clauses: list[str] = []
    params: list[object] = []
    if search.strip():
        like = f"%{search.strip()}%"
        clauses.append("(term LIKE ? OR definition LIKE ?)")
        params.extend([like, like])
    if source:
        clauses.append("source = ?")
        params.append(source)
    if verified is not None:
        clauses.append("verified = ?")
        params.append(int(verified))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 200)))
    with _conn(db_path) as conn:
        rows = conn.execute(
            f"SELECT id, term, definition, source, page, category, verified, created_at, updated_at "
            f"FROM glossary_terms {where} ORDER BY term COLLATE NOCASE ASC LIMIT ?",
            params,
        ).fetchall()
    return [{**dict(row), "verified": bool(row["verified"])} for row in rows]


def create_glossary_term(
    db_path: str | Path,
    term: str,
    definition: str,
    source: str = "",
    page: int | None = None,
    category: str = "Umum",
    verified: bool = False,
) -> dict:
    now = _now()
    with _conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO glossary_terms "
            "(term, definition, source, page, category, verified, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (term.strip(), definition.strip(), source.strip(), page, category.strip() or "Umum",
             int(verified), now, now),
        )
        term_id = cur.lastrowid
    return get_glossary_term(db_path, int(term_id)) or {}


def get_glossary_term(db_path: str | Path, term_id: int) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM glossary_terms WHERE id = ?", (term_id,)).fetchone()
    if row is None:
        return None
    return {**dict(row), "verified": bool(row["verified"])}


def update_glossary_term(
    db_path: str | Path,
    term_id: int,
    term: str,
    definition: str,
    source: str = "",
    page: int | None = None,
    category: str = "Umum",
    verified: bool = False,
) -> dict | None:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE glossary_terms SET term = ?, definition = ?, source = ?, page = ?, "
            "category = ?, verified = ?, updated_at = ? WHERE id = ?",
            (term.strip(), definition.strip(), source.strip(), page, category.strip() or "Umum",
             int(verified), _now(), term_id),
        )
    return get_glossary_term(db_path, term_id) if cur.rowcount else None


def delete_glossary_term(db_path: str | Path, term_id: int) -> bool:
    with _conn(db_path) as conn:
        cur = conn.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))
    return cur.rowcount > 0


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


# ----------------------------------------------------------------------
# Audit log (P0-02) — actor, action, status, durasi
# ----------------------------------------------------------------------
def record_audit(
    db_path: str | Path,
    actor: str,
    action: str,
    ip: str = "",
    status: int = 200,
    duration_ms: float = 0.0,
) -> None:
    """Catat satu aksi API yang terproteksi (idempotent-safe, jangan crash)."""
    try:
        with _conn(db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, actor, action, ip, status, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_now(), actor[:120], action[:300], ip[:60], status, duration_ms),
            )
    except sqlite3.Error:
        pass  # audit gagal tidak boleh menjatuhkan request


def list_audit(db_path: str | Path, limit: int = 50) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, action, ip, status, duration_ms "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# Document registry (P1-01/P1-02) — source of truth lifecycle file/index
# ----------------------------------------------------------------------
def register_document(
    db_path: str | Path,
    source: str,
    kind: str = "file",
    job_id: str = "",
    file_path: str = "",
    checksum: str = "",
    size_bytes: int = 0,
    category: str = "Umum",
    status: str = "queued",
) -> dict:
    """Daftarkan dokumen (atau mulai ulang versi barunya)."""
    now = _now()
    existing = get_document(db_path, source)
    version = (existing.get("version") or 0) + 1 if existing else 1
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT INTO documents (source, job_id, kind, file_path, checksum, "
            "size_bytes, category, status, chunks, error, version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?) "
            "ON CONFLICT(source) DO UPDATE SET "
            "job_id = excluded.job_id, kind = excluded.kind, "
            "file_path = excluded.file_path, checksum = excluded.checksum, "
            "size_bytes = excluded.size_bytes, category = excluded.category, "
            "status = excluded.status, error = '', "
            "version = documents.version + 1, updated_at = excluded.updated_at",
            (source, job_id, kind, file_path, checksum, size_bytes,
             category, status, version, now, now),
        )
    return get_document(db_path, source) or {
        "source": source, "status": status, "job_id": job_id, "version": version,
    }


def update_document_status(
    db_path: str | Path,
    source: str,
    status: str,
    *,
    error: str = "",
    chunks: int | None = None,
    file_path: str | None = None,
    checksum: str | None = None,
    category: str | None = None,
    job_id: str | None = None,
) -> None:
    sets = ["status = ?", "updated_at = ?"]
    params: list = [status, _now()]
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    if chunks is not None:
        sets.append("chunks = ?")
        params.append(chunks)
    if file_path is not None:
        sets.append("file_path = ?")
        params.append(file_path)
    if checksum is not None:
        sets.append("checksum = ?")
        params.append(checksum)
    if category is not None:
        sets.append("category = ?")
        params.append(category)
    if job_id is not None:
        sets.append("job_id = ?")
        params.append(job_id)
    params.append(source)
    with _conn(db_path) as conn:
        conn.execute(
            f"UPDATE documents SET {', '.join(sets)} WHERE source = ?", params
        )


def get_document(db_path: str | Path, source: str) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE source = ?", (source,)
        ).fetchone()
    return dict(row) if row else None


def get_document_by_job(db_path: str | Path, job_id: str) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE job_id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def list_document_registry(db_path: str | Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def purge_document(db_path: str | Path, source: str) -> None:
    """Hapus baris registry (dipakai saat purge total dokumen)."""
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM documents WHERE source = ?", (source,))


# ----------------------------------------------------------------------
# Retensi & clear-all (P0-03) — lifecycle data pribadi
# ----------------------------------------------------------------------
def purge_old_chats(db_path: str | Path, days: int) -> int:
    """Hapus session + pesan yang tidak diakses selama `days` hari.

    CASCADE menghapus messages & session_summaries. Return jumlah session
    yang dihapus. dipanggil saat startup bila RETAIN_CHAT_DAYS > 0.
    """
    if days <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with _conn(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE updated_at < ?", (cutoff,)
        )
    return cur.rowcount


def clear_all_user_data(db_path: str | Path) -> dict:
    """Hapus SEMUA data pribadi: chat, ringkasan, anotasi, quiz, kartu.

    Indeks dokumen (ChromaDB) TIDAK ikut dihapus di sini — gunakan
    reset/delete per dokumen untuk itu.
    """
    tables = [
        "sessions",            # cascade ke messages & session_summaries
        "annotations",
        "review_cards",
        "flashcards",
        "flashcard_stats",
        "quiz_attempts",
        "quiz_results",
        "glossary_terms",
    ]
    deleted: dict[str, int] = {}
    with _conn(db_path) as conn:
        for t in tables:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (t,),
            ).fetchone()
            if exists:
                cur = conn.execute(f"DELETE FROM {t}")
                deleted[t] = cur.rowcount
    return deleted


def clear_semantic_cache_entries(db_path: str | Path) -> int:
    """Kosongkan tabel cache jika ada (backend ChromaDB, bukan SQLite)."""
    # Cache semantic tinggal di ChromaDB (collection query_cache), bukan
    # SQLite — fungsi ini placeholder agar pemanggil tidak bergantung tabel.
    return 0
