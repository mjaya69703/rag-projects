"""Sample Review Cards Seeder for SM-2 Spaced Repetition."""

import sqlite3

SAMPLE_CARDS = [
    ("card_rag_01", "Apa perbedaan utama antara pencarian leksikal (BM25) dan vektor?", "AI & Search"),
    ("card_rag_02", "Bagaimana formula perhitungan efisiensi retrieval RRF (Reciprocal Rank Fusion)?", "RAG Engine"),
    ("card_rag_03", "Mengapa database WAL mode direkomendasikan untuk konkurensi SQLite?", "Database"),
]


def run(conn: sqlite3.Connection) -> int:
    inserted = 0
    for card_id, question, source in SAMPLE_CARDS:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO review_cards (card_id, question, source, next_due, interval_days, ease_factor, repetitions, lapses)
                VALUES (?, ?, ?, datetime('now'), 1.0, 2.5, 0, 0)
                """,
                (card_id, question, source),
            )
            inserted += 1
        except Exception:
            pass
    conn.commit()
    return inserted
