"""Test fitur belajar: spaced repetition, weak-spot, progress, quiz, flashcards.

Jalankan: pytest tests/test_learning.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, learning
from app.pdf_parser import parse_pdf
from app.rag_engine import RAGEngine
from app.vector_store import VectorStore
from tests.make_sample_pdf import make_sample_pdf


class FakeLLM:
    """LLM mock dengan respons teks yang bisa diatur."""

    def __init__(self, text: str = "Jawaban mock.") -> None:
        self.calls = 0
        self.text = text

    def chat(self, messages: list[dict], max_tokens: int = 1024) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(text=self.text, model="fake-model", usage=None)


def _make_store(tmp_path: Path) -> VectorStore:
    sample = tmp_path / "materi_jaringan.pdf"
    make_sample_pdf(sample)
    store = VectorStore(persist_dir=tmp_path / "chroma_test")
    chunks = parse_pdf(sample)
    store.add_documents(chunks, source=sample.name)
    return store


def _seed_repeated(path: Path, question: str, times: int) -> str:
    """Buat session + tanya berulang; return session id."""
    sid = db.create_session(path)["id"]
    for _ in range(times):
        db.add_message(path, sid, "user", question, [])
        db.add_message(path, sid, "assistant", "Jawaban.", [])
    return sid


def test_sync_due_answer_cards(tmp_path: Path) -> None:
    path = tmp_path / "review.db"
    db.init_db(path)
    _seed_repeated(path, "Apa itu VLAN?", 2)

    assert learning.sync_cards(path) == 1
    assert learning.sync_cards(path) == 0, "sync kedua tidak boleh duplikat"

    due = learning.due_cards(path)
    assert len(due) == 1
    card = due[0]
    assert card["question"] == "Apa itu VLAN?"
    assert card["interval_days"] == 1 and card["lapses"] == 0
    assert card["last_reviewed"] is None

    stats = learning.card_stats(path)
    assert stats["total"] == 1 and stats["due_today"] == 1 and stats["avg_lapses"] == 0.0

    # remembered: interval naik 2x, lapses reset
    c2 = learning.answer_card(path, card["card_id"], remembered=True)
    assert c2["interval_days"] == 2 and c2["lapses"] == 0
    assert c2["last_reviewed"] is not None
    assert learning.due_cards(path) == [], "kartu yang baru dijawab belum due"

    # forgotten: interval reset ke 1, lapses +1
    c3 = learning.answer_card(path, card["card_id"], remembered=False)
    assert c3["interval_days"] == 1 and c3["lapses"] == 1

    # remembered lagi setelah lupa: 1*2 = 2, lapses reset
    c4 = learning.answer_card(path, card["card_id"], remembered=True)
    assert c4["interval_days"] == 2 and c4["lapses"] == 0

    try:
        learning.answer_card(path, "tidak-ada", remembered=True)
        raise AssertionError("card_id tidak dikenal harus error")
    except ValueError:
        pass


def test_weak_spots_ordering(tmp_path: Path) -> None:
    path = tmp_path / "weak.db"
    db.init_db(path)
    _seed_repeated(path, "Apa itu VLAN?", 3)  # sering ditanya, kartunya bagus
    _seed_repeated(path, "bagaimana cara routing?", 2)

    learning.sync_cards(path)
    routing_card = next(
        c for c in learning.due_cards(path, limit=20) if "routing" in c["question"]
    )
    learning.answer_card(path, routing_card["card_id"], remembered=False)
    learning.answer_card(path, routing_card["card_id"], remembered=False)

    spots = learning.weak_spots(path)
    assert len(spots) == 2
    top = spots[0]
    assert "routing" in top["topic"], "lupa berulang harus jadi weak spot teratas"
    assert top["asked"] == 2 and top["lapses"] == 2 and top["wrong"] == 0
    assert top["score"] == 2 + 2 * 2, "skor = asked + lapses*2 + wrong*3"

    assert learning.weak_spots(path, limit=1)[0]["topic"] == top["topic"]


def test_document_progress_from_messages(tmp_path: Path) -> None:
    path = tmp_path / "progress.db"
    db.init_db(path)
    sid = db.create_session(path)["id"]
    db.add_message(
        path, sid, "assistant", "Jawaban 1",
        [
            {"source": "a.pdf", "page": 1, "heading": "VLAN"},
            {"source": "a.pdf", "page": 2, "heading": "Routing"},
        ],
    )
    db.add_message(
        path, sid, "assistant", "Jawaban 2",
        [{"source": "a.pdf", "page": 1, "heading": "VLAN"}],
    )
    db.add_message(
        path, sid, "assistant", "Jawaban 3",
        [{"source": "b.pdf", "page": 5, "heading": "OSPF"}],
    )

    progress = learning.document_progress(path)
    by_source = {e["source"]: e for e in progress}
    assert set(by_source) == {"a.pdf", "b.pdf"}

    a = by_source["a.pdf"]
    assert a["total_questions"] == 2, "satu pesan yang kutip 2 chunk tetap 1 tanya"
    assert a["headings_covered"] == [
        {"heading": "VLAN", "asked": 2},
        {"heading": "Routing", "asked": 1},
    ]
    assert by_source["b.pdf"]["total_questions"] == 1

    # headings_by_source: dokumen tanpa jejak di chat tetap dilaporkan
    full = learning.document_progress(path, headings_by_source={"a.pdf": [], "c.pdf": []})
    c = next(e for e in full if e["source"] == "c.pdf")
    assert c["headings_covered"] == [] and c["total_questions"] == 0


def test_generate_quiz_json_and_fallback(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        llm = FakeLLM(
            text='''```json
[
  {"question": "Apa itu VLAN?", "options": ["Partisi jaringan logis", "x", "y", "z"], "answer_index": 0},
  {"question": "Soal kedua", "options": ["a", "b", "c", "d"], "answer_index": 2},
  {"question": "Soal ketiga", "options": ["a", "b", "c", "d"], "answer_index": 9}
]
```'''
        )
        engine = RAGEngine(store=store, llm=llm)
        questions = learning.generate_quiz(engine, source="materi_jaringan.pdf", n=3)
        assert len(questions) == 3
        assert questions[0]["question"] == "Apa itu VLAN?"
        assert len(questions[0]["options"]) == 4
        assert questions[0]["answer_index"] == 0
        assert questions[2]["answer_index"] == 3, "answer_index di-clamp ke range opsi"
        assert llm.calls == 1

        # fallback: LLM tidak mengembalikan JSON -> 1 soal sederhana dari heading
        llm_bad = FakeLLM(text="Maaf, saya tidak bisa membuat soal.")
        engine_bad = RAGEngine(store=store, llm=llm_bad)
        fallback = learning.generate_quiz(engine_bad, source="materi_jaringan.pdf", n=3)
        assert len(fallback) == 1
        assert "membahas" in fallback[0]["question"]
        assert len(fallback[0]["options"]) == 4 and fallback[0]["answer_index"] == 0

        # source yang tidak ada -> tidak ada materi -> daftar kosong
        empty = learning.generate_quiz(engine, source="tidak-ada.pdf", n=3)
        assert empty == []
    finally:
        store.close()


def test_grade_quiz_parse(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        questions = [
            {"question": "Q1", "options": ["a", "b", "c", "d"], "answer_index": 0},
            {"question": "Q2", "options": ["a", "b", "c", "d"], "answer_index": 1},
            {"question": "Q3", "options": ["a", "b", "c", "d"], "answer_index": 2},
        ]
        llm = FakeLLM(
            text=(
                '{"score": 3, "total": 5, "feedback": "Lumayan", '
                '"details": [{"correct": true, "correct_index": 0, "explanation": "benar"}, '
                '{"correct": false, "correct_index": 1, "explanation": "salah"}, '
                '{"correct": true, "correct_index": 2, "explanation": "benar"}]}'
            )
        )
        engine = RAGEngine(store=store, llm=llm)
        result = learning.grade_quiz(engine, questions, [0, 1, 2])
        assert result["score"] == 3 and result["total"] == 5
        assert result["feedback"] == "Lumayan"
        assert len(result["details"]) == 3
        assert result["details"][1] == {
            "correct": True,  # user jawab 1 == correct_index 1
            "correct_index": 1,
            "explanation": "salah",
        }

        # parse gagal -> fallback deterministik (bandingkan answer_index)
        llm_bad = FakeLLM(text="saya tidak bisa menilai")
        engine_bad = RAGEngine(store=store, llm=llm_bad)
        fallback = learning.grade_quiz(engine_bad, questions, [0, 1, 2])
        assert fallback["score"] == 3, "fallback harus cocokkan kunci jawaban"
        assert fallback["total"] == len(questions)
        assert all(d["correct"] for d in fallback["details"])

        # tanpa soal -> total 0
        assert learning.grade_quiz(engine, [], []) == {
            "score": 0, "total": 0, "feedback": "", "details": [],
        }
    finally:
        store.close()


def test_flashcard_answer_and_stats(tmp_path: Path) -> None:
    """Tahu/belum flashcard tercatat & statistik urut paling sering salah."""
    path = tmp_path / "learn.db"
    db.init_db(path)
    learning.answer_flashcard(path, "VLAN", "materi.pdf", known=True)
    learning.answer_flashcard(path, "VLAN", "materi.pdf", known=False)
    learning.answer_flashcard(path, "OSPF", "materi.pdf", known=False)
    learning.answer_flashcard(path, "OSPF", "materi.pdf", known=False)

    stats = learning.flashcard_stats(path)
    assert len(stats) == 2
    by_heading = {s["heading"]: s for s in stats}
    assert by_heading["VLAN"]["known_count"] == 1
    assert by_heading["VLAN"]["unknown_count"] == 1
    assert by_heading["OSPF"]["unknown_count"] == 2
    # urut: OSPF (2 salah) di depan VLAN (1 salah)
    assert stats[0]["heading"] == "OSPF"


def test_quiz_history(tmp_path: Path) -> None:
    path = tmp_path / "quiz.db"
    db.init_db(path)
    learning.save_quiz_score(path, "a.pdf", 3, 5)
    learning.save_quiz_score(path, "b.pdf", 5, 5)
    learning.save_quiz_score(path, "a.pdf", 4, 5)

    history = learning.quiz_history(path)
    assert len(history) == 3
    assert history[0]["score"] == 4, "riwayat terbaru di depan"
    assert history[1]["source"] == "b.pdf"
    assert all(h["total"] == 5 for h in history)
    assert len(learning.quiz_history(path, limit=2)) == 2


def test_flashcards_from_store(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        cards = learning.flashcards(store)
        assert len(cards) >= 5
        assert all({"heading", "content"} <= set(c) for c in cards)
        headings = [c["heading"] for c in cards]
        assert len(headings) == len(set(headings)), "satu kartu per heading"

        filtered = learning.flashcards(store, source="materi_jaringan.pdf", limit=2)
        assert len(filtered) == 2
        assert learning.flashcards(store, source="tidak-ada.pdf") == []
    finally:
        store.close()


def main() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_sync_due_answer_cards(tmp_path)
        test_weak_spots_ordering(tmp_path)
        test_document_progress_from_messages(tmp_path)
        test_generate_quiz_json_and_fallback(tmp_path)
        test_grade_quiz_parse(tmp_path)
        test_flashcard_answer_and_stats(tmp_path)
        test_quiz_history(tmp_path)
        test_flashcards_from_store(tmp_path)
    print("\nSemua test learning PASS ✔")


if __name__ == "__main__":
    main()
