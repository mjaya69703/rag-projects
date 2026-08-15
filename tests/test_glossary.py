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
    def chat(self, messages, max_tokens):
        return SimpleNamespace(
            text='[{"term":"RAG","definition":"Pengambilan konteks sebelum generasi.","source":"materi.pdf","page":4,"category":"AI"}]'
        )


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
