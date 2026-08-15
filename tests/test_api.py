"""Test Sprint 4: FastAPI endpoint (upload, query, documents, delete).

Jalankan: python tests/test_api.py  atau  pytest tests/test_api.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

# Isolasi data & upload ke direktori sementara SEBELUM import app.main
_TMP = tempfile.mkdtemp()
os.environ["PERSIST_DIR"] = str(Path(_TMP) / "chroma")
os.environ["UPLOAD_DIR"] = str(Path(_TMP) / "uploads")
os.environ["DB_PATH"] = str(Path(_TMP) / "chat.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.rag_engine import RAGEngine
from tests.make_sample_pdf import make_sample_pdf


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.text = "Jawaban API mock."
        self.model = "fake-model"

    def chat(self, messages: list[dict], max_tokens: int = 1024) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(text=self.text, model="fake-model", usage=None)

    async def astream_chat(self, messages: list[dict], max_tokens: int = 1024):
        self.calls += 1
        yield self.text


def _sample_pdf() -> bytes:
    path = Path(_TMP) / "sample_api.pdf"
    make_sample_pdf(path)
    return path.read_bytes()


def _use_mock_llm(client: TestClient) -> FakeLLM:
    llm = FakeLLM()
    client.app.state.engine = RAGEngine(
        store=client.app.state.store, llm=llm
    )
    return llm


def _upload_wait(client: TestClient, **kwargs) -> dict:
    """Upload -> poll job sampai ready/error (kontrak ingestion asinkron)."""
    resp = client.post("/upload", **kwargs)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    if body.get("status") == "ready":  # dedup: tidak berubah
        return body
    assert body["status"] == "processing", body
    job_id = body["job_id"]
    job = None
    for _ in range(200):  # maks ~10 detik
        job = client.get(f"/jobs/{job_id}").json()["job"]
        if job["status"] in ("ready", "error"):
            break
        time.sleep(0.05)
    assert job is not None and job["status"] == "ready", job
    return {**body, "status": "ready", "chunks": job.get("chunks", 0)}


def test_health() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_full_flow() -> None:
    """Upload -> list -> query (mock LLM) -> delete."""
    with TestClient(app) as client:
        llm = _use_mock_llm(client)

        # upload (asinkron: poll job)
        data = _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        assert data["source"] == "sample_api.pdf"
        assert data["chunks"] > 0

        # list
        resp = client.get("/documents")
        docs = resp.json()["documents"]
        assert any(d["source"] == "sample_api.pdf" for d in docs), docs

        # query -> pakai mock LLM, jawaban konsisten, ada sumber
        resp = client.post("/query", json={"question": "Apa itu VLAN?"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"] == "Jawaban API mock."
        assert body["model"] == "fake-model"
        assert body["sources"], "query harus mengembalikan sumber"
        src = body["sources"][0]
        assert src["source"] == "sample_api.pdf"
        assert src["page"] >= 1
        assert src["heading"]
        assert llm.calls == 1

        # query yang sama -> dari cache (tanpa call LLM)
        resp = client.post("/query", json={"question": "Apa itu VLAN?"})
        assert resp.json()["cached"] is True
        assert llm.calls == 1

        # filter source
        resp = client.post(
            "/query", json={"question": "VLAN", "source": "sample_api.pdf"}
        )
        assert resp.status_code == 200
        assert all(s["source"] == "sample_api.pdf" for s in resp.json()["sources"])

        # delete
        resp = client.delete("/documents/sample_api.pdf")
        assert resp.status_code == 200
        assert resp.json()["removed"] > 0
        assert client.get("/documents").json()["documents"] == []


def test_upload_reject_unsupported_ext() -> None:
    """Ekstensi tidak didukung (.exe) -> 400."""
    with TestClient(app) as client:
        resp = client.post(
            "/upload",
            files={"file": ("program.exe", b"binary", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Format tidak didukung" in resp.json()["detail"]


def test_upload_markdown() -> None:
    """Markdown (.md) sekarang format didukung (fitur #10)."""
    with TestClient(app) as client:
        md = b"# Bab VLAN\n\nVLAN adalah metode mempartisi jaringan fisik.\n"
        body = _upload_wait(
            client,
            files={"file": ("catatan.md", md, "text/markdown")},
        )
        assert body["kind"] == "md"
        assert body["chunks"] > 0
        # query terhadap dokumen md bisa retrieve
        q = client.post("/query", json={"question": "VLAN", "source": "catatan.md"})
        assert q.status_code == 200


def test_query_empty_question() -> None:
    with TestClient(app) as client:
        resp = client.post("/query", json={"question": ""})
        assert resp.status_code == 422


def test_query_no_documents() -> None:
    """Store kosong -> pesan yang jelas, tanpa call LLM."""
    with TestClient(app) as client:
        _use_mock_llm(client)
        # Bersihkan dokumen dari test lain (state global TestClient)
        for doc in client.get("/documents").json()["documents"]:
            client.delete(f"/documents/{doc['source']}")
        resp = client.post("/query", json={"question": "ada isi apa?"})
        assert resp.status_code == 200
        body = resp.json()
        assert "Tidak ada" in body["answer"]
        assert body["sources"] == []


def test_stream_query_endpoint() -> None:
    """/query/stream: jawaban mengalir via SSE, tetap ada meta + done."""
    with TestClient(app) as client:
        llm = _use_mock_llm(client)
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        with client.stream(
            "POST", "/query/stream", json={"question": "Apa itu OSPF routing?"}
        ) as resp:
            assert resp.status_code == 200, resp.text
            body = "".join(resp.iter_text())

        assert "Jawaban API mock." in body
        assert '"type": "meta"' in body
        assert '"type": "delta"' in body
        assert '"type": "done"' in body
        assert '"sources"' in body
        assert llm.calls == 1


def test_delete_not_found() -> None:
    with TestClient(app) as client:
        resp = client.delete("/documents/tidak-ada.pdf")
        assert resp.status_code == 404


def test_repeated_questions_endpoint() -> None:
    """Termometer: pertanyaan yang diulang terhitung dari pesan session."""
    with TestClient(app) as client:
        _use_mock_llm(client)
        sid = client.post("/sessions/create").json()["session"]["id"]
        question = "pertanyaan termometer yang unik"
        for _ in range(2):
            resp = client.post(
                "/query", json={"question": question, "session_id": sid}
            )
            assert resp.status_code == 200, resp.text

        data = client.get("/repeated-questions").json()
        assert data["status"] == "ok"
        assert data["days"] == 7
        assert data["usage"]["sessions_active"] >= 1
        assert data["usage"]["questions"] >= 2
        matches = [q for q in data["questions"] if q["question"] == question]
        assert matches and matches[0]["count"] == 2


def test_query_deleted_document_grounding() -> None:
    """Query ke dokumen yang sudah dihapus -> respon jelas tanpa LLM."""
    with TestClient(app) as client:
        llm = _use_mock_llm(client)
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        client.delete("/documents/sample_api.pdf")
        assert client.get("/deleted-documents").json()["documents"][0]["source"] == "sample_api.pdf"

        resp = client.post(
            "/query", json={"question": "isi apa?", "source": "sample_api.pdf"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["document_missing"] is True
        assert "sudah dihapus" in body["answer"]
        assert body["sources"] == []
        assert llm.calls == 0, "dokumen hilang tidak boleh memanggil LLM"


def test_learning_flashcards_and_due() -> None:
    """Flashcards dari heading (fallback LLM) + kartu review jatuh tempo."""
    with TestClient(app) as client:
        _use_mock_llm(client)  # deterministik: jangan panggil LLM asli
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        cards = client.get("/learning/flashcards").json()["cards"]
        assert cards, "flashcards harus ada dari dokumen terindeks"
        assert all({"heading", "content"} <= set(c) for c in cards)

        # pertanyaan diulang (via session, supaya tersimpan) -> kartu review
        sid = client.post("/sessions/create").json()["session"]["id"]
        for _ in range(2):
            client.post("/query", json={"question": "Apa itu VLAN?", "session_id": sid})
        due = client.get("/learning/due").json()
        assert due["status"] == "ok"
        assert any("VLAN" in c["question"] for c in due["cards"])


def test_locations_endpoint() -> None:
    """'Where is X covered?': lokasi topik di semua dokumen."""
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        locs = client.get("/locations", params={"q": "VLAN"}).json()["locations"]
        assert locs
        assert locs[0]["source"] == "sample_api.pdf"
        assert client.get("/locations").json()["locations"] == []


def test_learning_mastery_endpoint() -> None:
    """Halaman Progress memanggil /learning/mastery — harus 200 dengan shape benar."""
    with TestClient(app) as client:
        resp = client.get("/learning/mastery")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert isinstance(body["mastery"], list)
        # alias /api juga tersedia
        assert client.get("/api/learning/mastery").status_code == 200


def test_learning_progress_shape() -> None:
    """Frontend membaca key `progress`; backend harus menyediakannya."""
    with TestClient(app) as client:
        resp = client.get("/learning/progress")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "progress" in body, "frontend baca key progress"
        assert "documents" in body, "konsumen lama masih pakai key documents"
        assert isinstance(body["progress"], list)


def test_learning_mindmap_endpoint() -> None:
    """Peta konsep dokumen (glossaryService.getMindmap)."""
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        resp = client.get("/learning/mindmap", params={"source": "sample_api.pdf"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["mindmap"]["name"] == "sample_api.pdf"


def test_frontend_api_surface() -> None:
    """Kontrak: tiap endpoint yang dipanggil frontend harus ada & method-nya
    benar — tidak boleh 404 (path salah) / 405 (method salah) / 500."""
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        _use_mock_llm(client)  # LLM mock untuk endpoint yang memanggil AI

        calls = [
            ("GET", "/health", None),
            ("GET", "/metrics", None),
            ("GET", "/documents", None),
            ("GET", "/categories", None),
            ("GET", "/sessions/list", None),
            ("POST", "/sessions/create", {"json": {"title": "kontrak"}}),
            ("GET", "/learning/due", None),
            ("GET", "/learning/cards", None),
            ("GET", "/learning/flashcards", None),
            ("GET", "/learning/flashcards/stats", None),
            ("GET", "/learning/weak-spots", None),
            ("GET", "/learning/mastery", None),
            ("GET", "/learning/progress", None),
            ("GET", "/learning/recommendations", None),
            ("GET", "/learning/quiz/history", None),
            ("GET", "/learning/mindmap", None),
            ("GET", "/learning/summary", {"params": {"source": "sample_api.pdf"}}),
            ("GET", "/glossary", None),
            ("GET", "/glossary/candidates", None),
            ("GET", "/annotations", None),
            ("GET", "/privacy/info", None),
            ("GET", "/repeated-questions", None),
            ("GET", "/locations", {"params": {"q": "VLAN"}}),
            ("GET", "/documents/sample_api.pdf/chunks", None),
            ("GET", "/audit", None),
            ("GET", "/deleted-documents", None),
        ]
        for method, path, kw in calls:
            resp = client.request(method, path, **(kw or {}))
            assert resp.status_code not in (404, 405, 500), (
                f"{method} {path} -> {resp.status_code} {resp.text[:200]}"
            )


def test_document_chunks_endpoint() -> None:
    """Preview isi dokumen: chunk ber-halaman untuk halaman Library."""
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        data = client.get("/documents/sample_api.pdf/chunks").json()
        assert data["status"] == "ok"
        assert data["chunks"], "harus ada chunk"
        first = data["chunks"][0]
        assert {"chunk_index", "page", "heading", "text"} <= set(first)
        assert [c["chunk_index"] for c in data["chunks"]] == sorted(
            c["chunk_index"] for c in data["chunks"]
        )


def test_flashcards_answer_endpoint() -> None:
    """Tahu/belum flashcard tercatat; stats muncul."""
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        resp = client.post(
            "/learning/flashcards/answer",
            json={"heading": "2.1 Pengertian VLAN", "source": "sample_api.pdf", "known": False},
        )
        assert resp.status_code == 200
        assert resp.json()["card"]["unknown_count"] == 1
        stats = client.get("/learning/flashcards/stats").json()["stats"]
        assert any(s["heading"] == "2.1 Pengertian VLAN" for s in stats)


def test_quiz_generate_up_to_20() -> None:
    """Jumlah soal bebas hingga 20; response punya attempt_id (P2-04)."""
    with TestClient(app) as client:
        resp = client.post("/learning/quiz/generate", json={"n": 20, "source": None})
        # 200 = ada materi; 400 = tidak ada materi; 502 = LLM error
        assert resp.status_code in (200, 400, 502), resp.text
        if resp.status_code == 200:
            body = resp.json()
            assert body["attempt_id"]
            assert all("answer_index" not in q for q in body["questions"])


def test_quiz_grade_returns_explanations() -> None:
    """Koreksi kuis mengembalikan pembahasan per soal (LLM batch, opsional).

    Skor tetap deterministik; pembahasan tidak memengaruhi skor.
    """
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        llm = _use_mock_llm(client)
        llm.text = json.dumps([
            {
                "question": "Apa fungsi VLAN?",
                "options": ["Partisi broadcast", "Enkripsi data", "Routing dinamis", "NAT"],
                "answer_index": 0,
            },
            {
                "question": "Apa itu OSPF?",
                "options": ["Distance vector", "Link-state routing", "Path vector", "Proprietary"],
                "answer_index": 1,
            },
        ])
        resp = client.post(
            "/learning/quiz/generate", json={"n": 2, "source": "sample_api.pdf"}
        )
        assert resp.status_code == 200, resp.text
        attempt_id = resp.json()["attempt_id"]

        # Tahap koreksi: LLM menghasilkan pembahasan
        llm.text = json.dumps(["VLAN memisahkan domain broadcast.", "OSPF adalah protokol link-state."])
        resp = client.post(
            "/learning/quiz/grade",
            json={"attempt_id": attempt_id, "answers": [0, 1]},
        )
        assert resp.status_code == 200, resp.text
        details = resp.json()["details"]
        assert len(details) == 2
        assert all(d.get("explanation") for d in details), "pembahasan harus ada"
        assert resp.json()["score"] == 2

        # LLM gagal / respons tak valid -> tetap 200 tanpa pembahasan
        llm.text = "bukan json"
        resp = client.post(
            "/learning/quiz/grade",
            json={"attempt_id": attempt_id, "answers": [0, 1]},
        )
        assert resp.status_code == 200, resp.text
        assert all("explanation" not in d for d in resp.json()["details"])


def test_quiz_attempt_detail_endpoint() -> None:
    """Riwayat kuis: detail attempt berisi soal + kunci jawaban + skor."""
    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        llm = _use_mock_llm(client)
        llm.text = json.dumps([
            {
                "question": "Apa fungsi VLAN?",
                "options": ["Partisi broadcast", "Enkripsi", "Routing", "NAT"],
                "answer_index": 0,
            },
        ])
        resp = client.post(
            "/learning/quiz/generate", json={"n": 1, "source": "sample_api.pdf"}
        )
        assert resp.status_code == 200, resp.text
        attempt_id = resp.json()["attempt_id"]

        # Belum dikerjakan: detail ada, skor kosong
        detail = client.get(f"/learning/quiz/attempts/{attempt_id}").json()
        assert detail["status"] == "ok"
        assert len(detail["questions"]) == 1
        assert detail["questions"][0]["correct_index"] == 0
        assert detail["score"] is None

        # Setelah dikoreksi: riwayat mencatat attempt_id & detail punya skor
        llm.text = "[" + json.dumps("Pembahasan VLAN.") + "]"
        client.post(
            "/learning/quiz/grade",
            json={"attempt_id": attempt_id, "answers": [0]},
        )
        hist = client.get("/learning/quiz/history").json()["history"]
        assert any(h.get("attempt_id") == attempt_id for h in hist), (
            "riwayat harus menautkan attempt_id"
        )
        detail = client.get(f"/learning/quiz/attempts/{attempt_id}").json()
        assert detail["score"] == 1
        assert detail["total"] == 1

        # Attempt tidak dikenal -> 404
        assert client.get("/learning/quiz/attempts/tidak-ada").status_code == 404


def test_annotations_crud() -> None:
    """Catatan pribadi pada chunk (fitur #9): simpan, list, hapus."""
    from urllib.parse import quote

    with TestClient(app) as client:
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )
        key = "sample_api.pdf#0"
        path = f"/annotations/{quote(key, safe='')}"
        resp = client.put(path, json={"note": "Ingat: VLAN access = 1 VLAN"})
        assert resp.status_code == 200
        assert resp.json()["annotation"]["note"] == "Ingat: VLAN access = 1 VLAN"

        notes = client.get("/annotations").json()["annotations"]
        assert any(a["chunk_key"] == key for a in notes)

        # update + hapus
        client.put(path, json={"note": "revisi"})
        assert client.delete(path).status_code == 200
        assert client.get("/annotations").json()["annotations"] == []


# ----------------------------------------------------------------------
# Multi-session chat
# ----------------------------------------------------------------------
def test_session_crud() -> None:
    with TestClient(app) as client:
        # create
        resp = client.post("/sessions/create")
        assert resp.status_code == 200
        sid = resp.json()["session"]["id"]
        assert resp.json()["session"]["title"] == "New Chat"

        # list
        assert any(s["id"] == sid for s in client.get("/sessions/list").json()["sessions"])

        # rename
        resp = client.put(f"/sessions/{sid}/rename", json={"title": "Chat Ujian"})
        assert resp.status_code == 200
        assert resp.json()["session"]["title"] == "Chat Ujian"

        # messages kosong
        assert client.get(f"/sessions/{sid}/messages").json()["messages"] == []

        # delete
        resp = client.delete(f"/sessions/{sid}")
        assert resp.status_code == 200
        assert client.get(f"/sessions/{sid}/messages").status_code == 404
        assert client.delete(f"/sessions/{sid}").status_code == 404


def test_session_query_saves_messages_and_auto_title() -> None:
    with TestClient(app) as client:
        llm = _use_mock_llm(client)
        sid = client.post("/sessions/create").json()["session"]["id"]

        # upload dulu biar ada dokumen
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )

        resp = client.post(
            "/query",
            json={"question": "Apa itu VLAN?", "session_id": sid},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"] == "Jawaban API mock."
        assert body["session"]["id"] == sid
        assert body["session"]["messages"] == 2
        assert body["session"]["tokens_est"] > 0

        # auto-title (bukan lagi "New Chat")
        session = [
            s for s in client.get("/sessions/list").json()["sessions"] if s["id"] == sid
        ][0]
        assert session["title"] != "New Chat"

        # pesan tersimpan: user + assistant dengan sources
        msgs = client.get(f"/sessions/{sid}/messages").json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "Apa itu VLAN?"
        assert msgs[1]["sources"], "jawaban harus simpan sumber"
        assert llm.calls == 1


def test_session_history_context() -> None:
    """Pertanyaan lanjutan memakai history -> cache tidak mencampuri."""
    with TestClient(app) as client:
        llm = _use_mock_llm(client)
        sid = client.post("/sessions/create").json()["session"]["id"]
        _upload_wait(
            client,
            files={"file": ("sample_api.pdf", _sample_pdf(), "application/pdf")},
        )

        r1 = client.post("/query", json={"question": "Apa itu VLAN?", "session_id": sid})
        assert r1.status_code == 200
        r2 = client.post(
            "/query",
            json={"question": "jelaskan lebih detail", "session_id": sid},
        )
        assert r2.status_code == 200
        # history non-empty -> cache di-skip -> LLM dipanggil lagi
        assert llm.calls == 2, "query dengan history harus memanggil LLM"

        msgs = client.get(f"/sessions/{sid}/messages").json()["messages"]
        assert len(msgs) == 4
        assert msgs[2]["role"] == "user" and msgs[2]["content"] == "jelaskan lebih detail"


def test_session_not_found() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/query", json={"question": "halo", "session_id": "tidak-ada"}
        )
        assert resp.status_code == 404


# ----------------------------------------------------------------------
# Validasi upload, rate limit, CORS (Sprint 5)
# ----------------------------------------------------------------------
def test_upload_reject_fake_pdf() -> None:
    """File .pdf palsu (isi bukan PDF) -> 400, bukan crash/500."""
    with TestClient(app) as client:
        resp = client.post(
            "/upload",
            files={"file": ("fake.pdf", b"plain text, not a pdf", "application/pdf")},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "File bukan PDF yang valid."


def test_upload_reject_corrupt_pdf() -> None:
    """PDF ber-magic %PDF tapi rusak -> job berakhir status=error, bukan 500."""
    with TestClient(app) as client:
        resp = client.post(
            "/upload",
            files={"file": ("corrupt.pdf", b"%PDF-1.7\n%%%%EOF", "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "processing"
        job = None
        for _ in range(200):  # maks ~10 detik
            job = client.get(f"/jobs/{body['job_id']}").json()["job"]
            if job["status"] in ("ready", "error"):
                break
            time.sleep(0.05)
        assert job is not None and job["status"] == "error", job
        assert job["error"]


def test_rate_limit_429() -> None:
    """qpm=2: request /query ke-3 ditolak 429; state di-reset sesudahnya."""
    with TestClient(app) as client:
        _use_mock_llm(client)
        main_module._RATE_LIMIT.clear()
        client.app.state.settings.rate_limit_qpm = 2
        try:
            assert (
                client.post("/query", json={"question": "tes satu"}).status_code == 200
            )
            assert (
                client.post("/query", json={"question": "tes dua"}).status_code == 200
            )
            r3 = client.post("/query", json={"question": "tes tiga"})
            assert r3.status_code == 429
            assert "Terlalu banyak" in r3.json()["detail"]
        finally:
            client.app.state.settings.rate_limit_qpm = 30  # kembalikan default
            main_module._RATE_LIMIT.clear()


def test_cors_header() -> None:
    """Origin yang diizinkan -> header CORS ada; origin asing -> tidak ada."""
    with TestClient(app) as client:
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.status_code == 200
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        )

        resp = client.get("/health", headers={"Origin": "http://evil.example.com"})
        assert resp.headers.get("access-control-allow-origin") is None


def test_custom_flashcards_and_deck_endpoints() -> None:
    """Test custom flashcard creation, list, and deletion."""
    with TestClient(app) as client:
        # Create custom card
        r1 = client.post(
            "/learning/flashcards/custom",
            json={"question": "Apa itu DNS?", "answer": "Domain Name System", "source": "test.pdf"},
        )
        assert r1.status_code == 200
        card_id = r1.json()["card"]["card_id"]
        assert card_id

        # List cards
        r2 = client.get("/learning/cards")
        assert r2.status_code == 200
        cards = r2.json()["cards"]
        assert any(c["card_id"] == card_id for c in cards)

        # Answer with rating 4
        r3 = client.post(
            "/learning/answer",
            json={"card_id": card_id, "rating": 4},
        )
        assert r3.status_code == 200
        assert r3.json()["card"]["interval_days"] >= 2

        # Delete card
        r4 = client.delete(f"/learning/flashcards/{card_id}")
        assert r4.status_code == 200


def test_learning_recommendations_endpoint() -> None:
    """Test learning recommendations endpoint."""
    with TestClient(app) as client:
        r = client.get("/learning/recommendations")
        assert r.status_code == 200
        assert "recommendations" in r.json()
        assert "card_stats" in r.json()


def test_toggle_verify_glossary_endpoint() -> None:
    """Test 1-click toggle verify glossary term."""
    with TestClient(app) as client:
        # Create term as draft
        r1 = client.post(
            "/glossary",
            json={"term": "BGP_TEST", "definition": "Border Gateway Protocol", "verified": False},
        )
        assert r1.status_code == 201
        term_id = r1.json()["term"]["id"]

        # Toggle to verified
        r2 = client.put(f"/glossary/{term_id}/verify")
        assert r2.status_code == 200
        assert r2.json()["term"]["verified"] is True

        # Toggle back to draft
        r3 = client.put(f"/glossary/{term_id}/verify")
        assert r3.status_code == 200
        assert r3.json()["term"]["verified"] is False

        # Cleanup
        client.delete(f"/glossary/{term_id}")


def main() -> None:
    test_health()
    test_full_flow()
    test_upload_reject_unsupported_ext()
    test_upload_markdown()
    test_query_empty_question()
    test_query_no_documents()
    test_delete_not_found()
    test_session_crud()
    test_session_query_saves_messages_and_auto_title()
    test_session_history_context()
    test_session_not_found()
    test_upload_reject_fake_pdf()
    test_upload_reject_corrupt_pdf()
    test_rate_limit_429()
    test_cors_header()
    test_query_deleted_document_grounding()
    test_learning_flashcards_and_due()
    test_locations_endpoint()
    test_document_chunks_endpoint()
    test_flashcards_answer_endpoint()
    test_quiz_generate_up_to_20()
    test_annotations_crud()
    test_custom_flashcards_and_deck_endpoints()
    test_learning_recommendations_endpoint()
    test_toggle_verify_glossary_endpoint()
    print("\nSemua test Sprint 4+session (API) PASS ✔")


if __name__ == "__main__":
    main()
