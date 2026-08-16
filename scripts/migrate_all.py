import sqlite3
from pathlib import Path


def migrate_db(db_path: Path):
    if not db_path.exists():
        print(f"DB {db_path} not found")
        return
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 1. review_cards
    rc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(review_cards)").fetchall()}
    if "ease_factor" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN ease_factor REAL NOT NULL DEFAULT 2.5")
    if "repetitions" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN repetitions INTEGER NOT NULL DEFAULT 0")
    if "answer" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN answer TEXT NOT NULL DEFAULT ''")
    if "created_at" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE review_cards SET created_at = datetime('now') WHERE created_at = ''")
    if "last_reviewed" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN last_reviewed TEXT")
    if "next_due" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN next_due TEXT NOT NULL DEFAULT ''")
    if "interval_days" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 1")
    if "lapses" not in rc_cols:
        conn.execute("ALTER TABLE review_cards ADD COLUMN lapses INTEGER NOT NULL DEFAULT 0")

    # 2. quiz_attempts
    qa_cols = {r["name"] for r in conn.execute("PRAGMA table_info(quiz_attempts)").fetchall()}
    if qa_cols:
        if "attempt_id" in qa_cols and "id" not in qa_cols:
            conn.execute("ALTER TABLE quiz_attempts RENAME COLUMN attempt_id TO id")
            qa_cols.add("id")
        if "questions_json" not in qa_cols:
            conn.execute("ALTER TABLE quiz_attempts ADD COLUMN questions_json TEXT NOT NULL DEFAULT '[]'")
        if "answer_key_json" not in qa_cols:
            conn.execute("ALTER TABLE quiz_attempts ADD COLUMN answer_key_json TEXT NOT NULL DEFAULT '[]'")
    else:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id              TEXT PRIMARY KEY,
            source          TEXT,
            questions_json  TEXT NOT NULL,
            answer_key_json TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
        """)

    # 2b. quiz_scores: tautkan skor ke attempt (untuk riwayat + pembahasan ulang)
    qs_cols = {r["name"] for r in conn.execute("PRAGMA table_info(quiz_scores)").fetchall()}
    if "attempt_id" not in qs_cols:
        conn.execute("ALTER TABLE quiz_scores ADD COLUMN attempt_id TEXT")

    # 3. documents
    doc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "checksum" not in doc_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN checksum TEXT NOT NULL DEFAULT ''")
    if "size_bytes" not in doc_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0")
    if "version" not in doc_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    if "created_at" not in doc_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

    # 4. glossary_terms
    glo_cols = {r["name"] for r in conn.execute("PRAGMA table_info(glossary_terms)").fetchall()}
    if "verified" not in glo_cols:
        conn.execute("ALTER TABLE glossary_terms ADD COLUMN verified INTEGER NOT NULL DEFAULT 0")

    conn.commit()
    conn.close()
    print(f"Migration completed successfully for {db_path}")

if __name__ == "__main__":
    migrate_db(Path("data/chat.db"))
