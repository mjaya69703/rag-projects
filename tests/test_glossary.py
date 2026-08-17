"""Test ekstraksi kandidat glossary tanpa memanggil provider LLM nyata."""

from __future__ import annotations

from types import SimpleNamespace

from app.glossary import extract_candidates


class FakeCollection:
    def get(self, **kwargs):
        return {
            "documents": ["RAG mengambil konteks relevan sebelum generasi jawaban."],
            "metadatas": [{"source": "materi.pdf", "page": 4, "heading": "RAG"}],
        }


class FakeLLM:
    def __init__(self, text: str | None = None) -> None:
        self.text = text or (
            '[{"term":"RAG","definition":"Pengambilan konteks sebelum generasi.","source":"materi.pdf","page":4,"category":"AI"}]'
        )

    def chat(self, messages, max_tokens):
        return SimpleNamespace(text=self.text, model="fake-model", usage=None)


def test_extract_candidates_normalizes_result() -> None:
    engine = SimpleNamespace(store=SimpleNamespace(collection=FakeCollection()), llm=FakeLLM())
    result = extract_candidates(engine, source="materi.pdf", limit=5)
    assert result == [{
        "term": "RAG",
        "definition": "Pengambilan konteks sebelum generasi.",
        "source": "materi.pdf",
        "page": 4,
        "category": "AI",
        "verified": False,
    }]


def test_extract_candidates_marks_existing_terms() -> None:
    """Kandidat yang sudah ada di glosarium ditandai ``exists: True``.

    Regression: UI dulu menerima kandidat duplikat karena backend tidak
    tahu istilah mana yang sudah tersimpan. Frontend sekarang
    menyembunyikan tombol Promosikan untuk ``exists=True``.
    """
    llm_text = (
        '[{"term":"RAG","definition":"Pengambilan konteks sebelum generasi.","source":"materi.pdf","page":4,"category":"AI"},'
        '{"term":"Embedding","definition":"Representasi vektor dokumen.","source":"materi.pdf","page":5,"category":"AI"}]'
    )
    engine = SimpleNamespace(
        store=SimpleNamespace(collection=FakeCollection()),
        llm=FakeLLM(text=llm_text),
    )
    result = extract_candidates(
        engine, source="materi.pdf", limit=5, existing_terms={"rag"}
    )
    assert len(result) == 2
    by_term = {item["term"]: item for item in result}
    assert by_term["RAG"]["exists"] is True
    assert by_term["Embedding"]["exists"] is False


def test_extract_candidates_dedupes_within_batch() -> None:
    """LLM kadang mengirim istilah sama dua kali — harus tetap 1 hasil."""
    engine = SimpleNamespace(
        store=SimpleNamespace(collection=FakeCollection()),
        llm=FakeLLM(
            text='[{"term":"RAG","definition":"Definisi A","source":"materi.pdf","page":4,"category":"AI"},'
            '{"term":"rag","definition":"Definisi B duplikat","source":"materi.pdf","page":4,"category":"AI"}]'
        ),
    )
    result = extract_candidates(engine, source="materi.pdf", limit=5)
    assert len(result) == 1
    assert result[0]["term"] == "RAG"
    assert result[0]["definition"] == "Definisi A"
