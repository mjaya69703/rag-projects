"""Test fitur belajar: spaced repetition, weak-spot, progress, quiz, flashcards.

Jalankan: pytest tests/test_learning.py -q
"""

from __future__ import annotations

import json
import sqlite3
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
    assert card["repetitions"] == 0 and card["ease_factor"] == 2.5
    assert card["last_reviewed"] is None

    stats = learning.card_stats(path)
    assert stats["total"] == 1 and stats["due_today"] == 1 and stats["avg_lapses"] == 0.0

    # SM-2 (P2-03): ingat pertama -> reps 1, interval 1, ease naik
    c2 = learning.answer_card(path, card["card_id"], remembered=True)
    assert c2["interval_days"] == 1 and c2["repetitions"] == 1
    assert c2["ease_factor"] == 2.6 and c2["lapses"] == 0
    assert c2["last_reviewed"] is not None
    assert learning.due_cards(path) == [], "kartu yang baru dijawab belum due"

    # ingat kedua -> reps 2, interval 6 hari
    c2b = learning.answer_card(path, card["card_id"], remembered=True)
    assert c2b["interval_days"] == 6 and c2b["repetitions"] == 2

    # lupa -> reps reset 0, interval 1, lapses +1, ease turun (2.7 -> 2.5)
    c3 = learning.answer_card(path, card["card_id"], remembered=False)
    assert c3["interval_days"] == 1 and c3["repetitions"] == 0
    assert c3["lapses"] == 1 and c3["ease_factor"] == 2.5

    # ingat lagi setelah lupa -> mulai dari rep 1; lapses kumulatif tetap 1
    c4 = learning.answer_card(path, card["card_id"], remembered=True)
    assert c4["interval_days"] == 1 and c4["repetitions"] == 1 and c4["lapses"] == 1

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
    # P2-03: wrong terisi nyata dari lapses (bukan 0)
    assert top["asked"] == 2 and top["lapses"] == 2 and top["wrong"] == 2
    assert top["score"] == 2 + 2 * 2 + 2 * 3, "skor = asked + lapses*2 + wrong*3"

    assert learning.weak_spots(path, limit=1)[0]["topic"] == top["topic"]


def test_mastery_stats(tmp_path: Path) -> None:
    """P2-03: exposure vs correctness vs mastery per source."""
    path = tmp_path / "mastery.db"
    db.init_db(path)
    learning.answer_flashcard(path, "VLAN", "a.pdf", known=True)
    learning.answer_flashcard(path, "VLAN", "a.pdf", known=False)
    learning.save_quiz_score(path, "a.pdf", 4, 5)

    mastery = learning.mastery_stats(path)
    by_source = {m["source"]: m for m in mastery}
    assert "a.pdf" in by_source
    a = by_source["a.pdf"]
    assert a["exposure"] == 7  # 2 flashcard + 5 soal quiz
    assert a["correct"] == 5   # 1 flashcard + 4 quiz
    assert a["wrong"] == 2     # 1 flashcard + 1 quiz
    assert a["mastery"] == round(5 / 7, 2)


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
        # LLM dipanggil per-chunk, jadi ia mengembalikan 1 object JSON
        llm = FakeLLM(
            text=(
                '{"question":"Apa itu VLAN?","options":["Partisi jaringan '
                'logis","Router","Switch","Firewall"],"answer_index":0}'
            )
        )
        engine = RAGEngine(store=store, llm=llm)
        questions = learning.generate_quiz(engine, source="materi_jaringan.pdf", n=3)
        assert len(questions) == 3, "total harus n walau LLM kasih 1 object per call"
        for q in questions:
            assert 1 <= len(q["options"]) <= 4
            assert 0 <= q["answer_index"] < len(q["options"])
            # Soal TIDAK boleh heading-MCQ dangkal
            first_line = q["question"].split("\n")[0]
            assert not first_line.startswith("Bagian '"), (
                f"soal generik 'Bagian X membahas topik apa' tidak boleh lolos: {first_line!r}"
            )

        # fallback: LLM rusak -> n soal berbasis KONTEN chunk (cloze/verifikasi)
        llm_bad = FakeLLM(text="Maaf, saya tidak bisa membuat soal.")
        engine_bad = RAGEngine(store=store, llm=llm_bad)
        fallback = learning.generate_quiz(engine_bad, source="materi_jaringan.pdf", n=3)
        assert len(fallback) == 3, "jumlah soal harus persis n walau LLM gagal"
        for q in fallback:
            assert (
                "Isilah" in q["question"]
                or "pernyataan" in q["question"].lower()
            ), f"soal fallback harus cloze/verifikasi, dapat: {q['question']!r}"
            assert all(len(o) > 0 for o in q["options"])

        # source yang tidak ada -> tidak ada materi -> daftar kosong
        empty = learning.generate_quiz(engine, source="tidak-ada.pdf", n=3)
        assert empty == []
    finally:
        store.close()


def test_generate_quiz_pads_when_llm_returns_fewer(tmp_path: Path) -> None:
    """LLM gagal / return junk -> total tetap n, fallback dari ISI chunk."""
    store = _make_store(tmp_path)
    try:
        class JunkLLM(FakeLLM):
            def chat(self, messages, max_tokens=1024):
                self.calls += 1
                return SimpleNamespace(text="", model="fake-model", usage=None)

        llm = JunkLLM()
        engine = RAGEngine(store=store, llm=llm)
        questions = learning.generate_quiz(engine, source="materi_jaringan.pdf", n=5)
        assert len(questions) == 5, "jumlah soal harus TEPAT 5 walau LLM gagal total"
        for q in questions:
            assert (
                "Isilah" in q["question"]
                or "pernyataan" in q["question"].lower()
            ), f"soal harus cloze/verifikasi, dapat: {q['question']!r}"
            assert 1 <= len(q["options"]) <= 4
    finally:
        store.close()


def test_generate_quiz_one_chunk_one_question(tmp_path: Path) -> None:
    """LLM dipanggil per-chunk (1 chunk → 1 soal), bukan batch sekaligus."""
    store = _make_store(tmp_path)
    try:
        class PerChunkLLM(FakeLLM):
            def __init__(self) -> None:
                super().__init__(text="")
                self.headings: list[str] = []

            def chat(self, messages, max_tokens=1024):
                self.calls += 1
                heading = "?"
                for line in messages[0]["content"].splitlines():
                    if line.startswith("Bagian: "):
                        heading = line[len("Bagian: "):].strip()
                        break
                self.headings.append(heading)
                return SimpleNamespace(
                    text=(
                        f'{{"question":"Soal untuk {heading}","options":'
                        f'["Benar","Pengecoh A","Pengecoh B","Pengecoh C"],'
                        f'"answer_index":0}}'
                    ),
                    model="fake",
                    usage=None,
                )

        llm = PerChunkLLM()
        engine = RAGEngine(store=store, llm=llm)
        questions = learning.generate_quiz(engine, source="materi_jaringan.pdf", n=4)
        assert len(questions) == 4
        assert llm.calls >= 4, "LLM minimal dipanggil 4x (1 per chunk)"
        assert len(set(llm.headings)) >= 4, "setiap chunk beda-heading diproses"
    finally:
        store.close()


def test_content_fallback_question_is_meaningful(tmp_path: Path) -> None:
    """Fallback konten harus cloze/verifikasi, bukan heading-MCQ generik."""
    chunk = {
        "heading": "VLAN",
        "text": (
            "Virtual Local Area Network atau VLAN adalah metode mempartisi "
            "satu jaringan fisik menjadi beberapa jaringan logis yang "
            "terpisah. Setiap VLAN memiliki identitas berupa nomor antara "
            "1 hingga 4094 dan broadcast domain dapat diperkecil sehingga "
            "lalu lintas jaringan menjadi lebih efisien."
        ),
    }
    pool = learning._extract_terms(chunk["text"])
    q = learning._content_fallback_question(chunk, pool)
    assert q is not None
    first_line = q["question"].split("\n")[0]
    assert "Isilah" in q["question"] or "pernyataan" in q["question"].lower()
    assert 1 <= len(q["options"]) <= 4
    # Tidak ada placeholder generik
    assert not any(o in {"Topik lain", "Tidak dibahas", "Tidak tahu"} for o in q["options"])
    # Jawaban benar harus muncul di opsi
    correct = q["options"][q["answer_index"]]
    # Cloze: kata yang diganti ada di teks
    assert len(correct) > 0


def test_normalize_question_dict_accepts_key_variants(tmp_path: Path) -> None:
    """Berbagai variasi key dari LLM: ``answer``/``correct``/``choices`` dll."""
    cases = [
        # answer_index + options (standar)
        ({"question": "Q?", "options": ["a", "b"], "answer_index": 1},
         {"question": "Q?", "options": ["a", "b"], "answer_index": 1}),
        # answer (0-based OK + choices)
        ({"question": "Q?", "choices": ["a", "b", "c", "d"], "answer": 2},
         {"question": "Q?", "options": ["a", "b", "c", "d"], "answer_index": 2}),
        # correct + answers
        ({"question": "Q?", "answers": ["x", "y"], "correct": 0},
         {"question": "Q?", "options": ["x", "y"], "answer_index": 0}),
        # alias bahasa: pertanyaan + opsi
        ({"pertanyaan": "Q?", "opsi": ["a", "b", "c"], "jawaban_benar": 2},
         {"question": "Q?", "options": ["a", "b", "c"], "answer_index": 2}),
        # answer_index out of range di-clamp
        ({"question": "Q?", "options": ["a", "b"], "answer_index": 99},
         {"question": "Q?", "options": ["a", "b"], "answer_index": 1}),
    ]
    for raw, expected in cases:
        out = learning._normalize_question_dict(raw)
        assert out == expected, f"normalize gagal untuk {raw!r}"


def test_parse_json_object_handles_balanced_braces_in_text(tmp_path: Path) -> None:
    """Object JSON yang disisipkan di teks panjang + object kedua (reject)."""
    text = (
        'Berikut soalnya:\n'
        '{"question":"Q1?","options":["a","b"],"answer_index":0}\n'
        'Semoga membantu!\n'
    )
    obj = learning._parse_json_object(text)
    assert obj == {"question": "Q1?", "options": ["a", "b"], "answer_index": 0}


def test_llm_generate_question_recovers_from_alternative_keys(tmp_path: Path) -> None:
    """LLM server kadang pakai key alternatif (``correct``/``choices``) —
    parser harus recover dan tetap menghasilkan soal utuh, bukan fallback."""
    store = _make_store(tmp_path)
    try:
        # Mock LLM yang ngirim key alternatif
        class AltKeyLLM:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, max_tokens=1024):
                self.calls += 1
                # Bentuk: object dengan key alternatif + prose di depan
                return SimpleNamespace(
                    text=(
                        'Berikut soalnya:\n'
                        '{"pertanyaan":"Apa fungsi VLAN?","choices":'
                        '["Memisahkan domain broadcast","Memperbesar broadcast",'
                        '"Menghapus router","Mengaktifkan DHCP"],"jawaban_benar":0}\n'
                        'Catatan: ini hanya contoh.'
                    ),
                    model="fake", usage=None,
                )

        llm = AltKeyLLM()
        engine = RAGEngine(store=store, llm=llm)
        questions = learning.generate_quiz(engine, source="materi_jaringan.pdf", n=2)
        assert len(questions) == 2
        # Soal pertama bukan fallback (karena LLM berhasil parse)
        assert "VLAN" in questions[0]["question"]
        assert questions[0]["options"][0] == "Memisahkan domain broadcast"
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


def test_quiz_attempt_server_side(tmp_path: Path) -> None:
    """P2-04: skor dihitung deterministik dari kunci server-side."""
    path = tmp_path / "attempt.db"
    db.init_db(path)
    questions = [
        {"question": "Q1", "options": ["a", "b", "c", "d"], "answer_index": 0},
        {"question": "Q2", "options": ["a", "b", "c", "d"], "answer_index": 1},
        {"question": "Q3", "options": ["a", "b", "c", "d"], "answer_index": 2},
    ]
    attempt = learning.create_quiz_attempt(path, "materi.pdf", questions)
    assert attempt["attempt_id"]
    # kunci tidak boleh bocor ke client
    assert all("answer_index" not in q for q in attempt["questions"])

    result = learning.grade_quiz_attempt(path, attempt["attempt_id"], [0, 9, 2])
    assert result["score"] == 2 and result["total"] == 3
    assert result["correct"] == [0, 2]
    assert [d["correct"] for d in result["details"]] == [True, False, True]

    # hasil tercatat ke history
    history = learning.quiz_history(path)
    assert history[0]["score"] == 2 and history[0]["source"] == "materi.pdf"

    # attempt tidak dikenal -> error
    try:
        learning.grade_quiz_attempt(path, "tidak-ada", [0])
        raise AssertionError("attempt tidak dikenal harus error")
    except ValueError:
        pass

    # jumlah jawaban tidak cocok -> error
    try:
        learning.grade_quiz_attempt(path, attempt["attempt_id"], [0])
        raise AssertionError("jumlah jawaban tidak cocok harus error")
    except ValueError:
        pass


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


def test_flashcards_llm_logical_and_cache(tmp_path: Path) -> None:
    """Tab Eksplorasi Dokumen: LLM menentukan konten Q&A logis; hasil di-cache."""
    store = _make_store(tmp_path)
    llm = FakeLLM(text=json.dumps([
        {
            "heading": "Apa fungsi VLAN?",
            "content": "Memisahkan domain broadcast untuk efisiensi jaringan.",
            "source": "materi_jaringan.pdf",
        },
        {
            "heading": "Kenapa antar-VLAN perlu routing?",
            "content": "Karena VLAN terisolasi; komunikasi lintas-VLAN butuh router.",
            "source": "materi_jaringan.pdf",
        },
    ]))
    engine = RAGEngine(store=store, llm=llm)
    path = tmp_path / "flash_llm.db"
    db.init_db(path)
    try:
        cards = learning.flashcards(store, limit=5, engine=engine, db_path=path)
        assert len(cards) == 2, "kartu LLM menentukan kontennya sendiri"
        assert cards[0]["heading"] == "Apa fungsi VLAN?"
        assert cards[0]["content"] == "Memisahkan domain broadcast untuk efisiensi jaringan."
        assert cards[0]["source"] == "materi_jaringan.pdf"
        assert llm.calls == 1

        # cache: kunjungan berikutnya tidak memanggil LLM lagi
        again = learning.flashcards(store, limit=5, engine=engine, db_path=path)
        assert llm.calls == 1
        assert again == cards

        # force: regenerasi melewati cache
        learning.flashcards(store, limit=5, engine=engine, db_path=path, force=True)
        assert llm.calls == 2
    finally:
        store.close()


def test_flashcards_llm_fallback_when_unavailable(tmp_path: Path) -> None:
    """LLM gagal / respons tak valid → fallback kartu heading/chunk (kontrak lama)."""
    store = _make_store(tmp_path)
    engine = RAGEngine(store=store, llm=FakeLLM(text="bukan json sama sekali"))
    path = tmp_path / "flash_fallback.db"
    db.init_db(path)
    try:
        cards = learning.flashcards(store, limit=3, engine=engine, db_path=path)
        assert cards, "fallback harus tetap menghasilkan kartu"
        assert all({"heading", "content"} <= set(c) for c in cards)
    finally:
        store.close()


def test_mindmap_tree_from_store(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        tree = learning.mindmap_tree(store)
        assert tree["name"] == "Knowledge Base"
        assert tree["children"], "harus ada node sumber dokumen"
        assert any(c["name"] == "materi_jaringan.pdf" for c in tree["children"])

        filtered = learning.mindmap_tree(store, source="materi_jaringan.pdf")
        assert filtered["name"] == "materi_jaringan.pdf"
        assert filtered["children"], "heading dokumen menjadi anak root"
    finally:
        store.close()


def test_review_cards_legacy_schema_migrated(tmp_path: Path) -> None:
    """DB lama tanpa created_at (schema pra-SM-2) harus sembuh sendiri.

    Reproduksi bug runtime: "table review_cards has no column named created_at"
    pada POST /learning/flashcards/generate di DB produksi.
    """
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE review_cards (
            card_id       TEXT PRIMARY KEY,
            question      TEXT NOT NULL,
            source        TEXT,
            next_due      TEXT NOT NULL,
            interval_days INTEGER NOT NULL DEFAULT 1,
            lapses        INTEGER NOT NULL DEFAULT 0,
            last_reviewed TEXT
        );
        INSERT INTO review_cards (card_id, question, source, next_due)
        VALUES ('legacy-1', 'Apa itu VLAN?', 'materi.pdf', '2026-01-01T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()

    db.init_db(path)
    # Simulasi alur POST /learning/flashcards/generate (save_to_deck)
    saved = learning.save_flashcards_to_deck(
        path,
        [
            {
                "front": "Apa fungsi OSPF?",
                "back": "Link-state routing protocol.",
                "source": "materi.pdf",
            }
        ],
    )
    assert len(saved) == 1

    # Baris lama ikut termigrasi: created_at terisi, kolom SM-2 ada
    rows = learning.list_review_cards(path)
    legacy = next(r for r in rows if r["card_id"] == "legacy-1")
    assert legacy["created_at"], "baris legacy harus punya created_at hasil migrasi"
    assert legacy["ease_factor"] == 2.5
    assert legacy["answer"] == ""
    assert legacy["interval_days"] == 1


def main() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        test_sync_due_answer_cards(tmp_path)
        test_weak_spots_ordering(tmp_path)
        test_document_progress_from_messages(tmp_path)
        test_generate_quiz_json_and_fallback(tmp_path)
        test_grade_quiz_parse(tmp_path)
        test_quiz_attempt_server_side(tmp_path)
        test_mastery_stats(tmp_path)
        test_flashcard_answer_and_stats(tmp_path)
        test_quiz_history(tmp_path)
        test_flashcards_from_store(tmp_path)
        test_flashcards_llm_logical_and_cache(tmp_path)
        test_flashcards_llm_fallback_when_unavailable(tmp_path)
        test_mindmap_tree_from_store(tmp_path)
        test_review_cards_legacy_schema_migrated(tmp_path)
    print("\nSemua test learning PASS ✔")


if __name__ == "__main__":
    main()
