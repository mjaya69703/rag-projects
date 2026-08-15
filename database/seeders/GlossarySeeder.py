"""Glossary Seeder with essential concepts."""

import sqlite3

SAMPLE_TERMS = [
    ("RAG", "Retrieval-Augmented Generation: arsitektur penggabungan dokumen relevan ke prompt LLM.", "Arsitektur", 1, "AI", 1),
    ("Vector Embedding", "Representasi numerik teks dalam ruang multi-dimensi untuk pencarian semantik.", "AI", 1, "AI", 1),
    ("BM25", "Algoritma pencarian leksikal berbasis probabilitas frekuensi kemunculan kata kunci.", "Search", 1, "Pencarian", 1),
    ("SM-2", "Algoritma SuperMemo-2 untuk penjadwalan pengulangan memori berkala (Spaced Repetition).", "Belajar", 1, "Edukasi", 1),
    ("Cosine Similarity", "Metrik matematika pengukur sudut kemiripan antara dua vektor representasi.", "Math", 1, "AI", 1),
]


def run(conn: sqlite3.Connection) -> int:
    inserted = 0
    for term, definition, source, page, category, verified in SAMPLE_TERMS:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO glossary (term, definition, source, page, category, verified)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (term, definition, source, page, category, verified),
            )
            inserted += 1
        except Exception:
            pass
    conn.commit()
    return inserted
