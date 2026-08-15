"""Test keamanan & privasi (P0-02/P0-03) + registry ingestion (P1-01/P1-02).

Fokus:
- Fail-closed auth: tanpa token -> 401 di endpoint data/mutasi; /health publik.
- Audit log mencatat aksi API terproteksi.
- Privacy disclosure (/privacy/info) + clear-all (/privacy/data) + clear cache.
- Upload asinkron: job registry + dedup checksum (tanpa load model HF).

Jalankan: pytest tests/test_auth.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Isolasi data ke direktori sementara SEBELUM import app.main
_TMP = tempfile.mkdtemp()
os.environ["PERSIST_DIR"] = str(Path(_TMP) / "chroma")
os.environ["UPLOAD_DIR"] = str(Path(_TMP) / "uploads")
os.environ["DB_PATH"] = str(Path(_TMP) / "chat.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app

TOKEN = "test-token-123"


def _auth(client: TestClient) -> dict:
    """Aktifkan auth + kembalikan header. Settings di-set per-instance
    supaya test tidak bergantung env global (robust kalau test lain
    meng-import app.main lebih dulu)."""
    client.app.state.settings.api_token = TOKEN
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health_public() -> None:
    """/health tetap publik (dipakai systemd/load balancer)."""
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_api_requires_token() -> None:
    """Tanpa kredensial -> 401 di endpoint data/mutasi (fail-closed)."""
    with TestClient(app) as client:
        _auth(client)
        for method, path in [
            ("GET", "/documents"),
            ("GET", "/metrics"),
            ("GET", "/sessions/list"),
            ("GET", "/locations"),
            ("GET", "/audit"),
            ("POST", "/query"),
            ("POST", "/sessions/create"),
            ("DELETE", "/privacy/data"),
        ]:
            resp = client.request(
                method, path, json={} if method == "POST" else None
            )
            assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


def test_api_with_token_ok() -> None:
    with TestClient(app) as client:
        headers = _auth(client)
        assert client.get("/documents", headers=headers).status_code == 200
        assert client.get("/metrics", headers=headers).status_code == 200


def test_wrong_token_rejected() -> None:
    with TestClient(app) as client:
        _auth(client)
        resp = client.get("/documents", headers={"Authorization": "Bearer salah"})
        assert resp.status_code == 401


def test_spa_static_public() -> None:
    """Halaman SPA (bukan API) tidak diblokir auth."""
    with TestClient(app) as client:
        _auth(client)
        resp = client.get("/")
        assert resp.status_code != 401  # statis/fallback SPA tetap dilayani


def test_audit_log_records_protected_actions() -> None:
    """Aksi API terproteksi tercatat di audit log (actor=token)."""
    with TestClient(app) as client:
        headers = _auth(client)
        client.get("/documents", headers=headers)
        client.get("/sessions/list", headers=headers)
        entries = client.get("/audit", headers=headers).json()["entries"]
        actions = [e["action"] for e in entries]
        assert any("GET /documents" in a for a in actions)
        assert any("GET /sessions/list" in a for a in actions)
        # Semua entri yang dibuat dengan token tercatat sebagai actor "token"
        assert any(e["actor"] == "token" for e in entries)


def test_privacy_info_disclosure() -> None:
    """/privacy/info menyediakan disclosure + retensi (P0-03)."""
    with TestClient(app) as client:
        headers = _auth(client)
        data = client.get("/privacy/info", headers=headers).json()
        assert data["status"] == "ok"
        assert data["external_data_flow"] is True
        assert "disclosure_text" in data
        assert "retention" in data
        assert data["provider_label"]


def test_clear_all_user_data() -> None:
    """DELETE /privacy/data menghapus session/chat (bukan indeks dokumen)."""
    with TestClient(app) as client:
        headers = _auth(client)
        sid = client.post("/sessions/create", headers=headers).json()["session"]["id"]
        assert (
            client.get(f"/sessions/{sid}/messages", headers=headers).status_code == 200
        )
        resp = client.delete("/privacy/data", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"].get("sessions", 0) >= 1
        assert (
            client.get(f"/sessions/{sid}/messages", headers=headers).status_code == 404
        )


def test_clear_cache_endpoint() -> None:
    with TestClient(app) as client:
        headers = _auth(client)
        resp = client.delete("/privacy/cache", headers=headers)
        assert resp.status_code == 200
        assert "cleared_entries" in resp.json()


def test_ingest_job_registry_and_dedup() -> None:
    """Upload asinkron: job registry + dedup checksum (tanpa model HF)."""
    import app.vector_store as vs

    with TestClient(app) as client:
        headers = _auth(client)
        orig = vs.VectorStore.replace_document
        vs.VectorStore.replace_document = (
            lambda self, chunks, source, category="Umum": len(list(chunks))
        )
        try:
            md = b"# Topik\n\nKonten singkat untuk uji registry.\n"
            resp = client.post(
                "/upload",
                files={"file": ("reg.md", md, "text/markdown")},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status"] == "processing"
            job = client.get(f"/jobs/{body['job_id']}", headers=headers).json()["job"]
            assert job["status"] == "ready", job
            assert job["checksum"]
            assert job["chunks"] > 0

            # dedup: konten sama -> langsung ready, tanpa job baru
            resp2 = client.post(
                "/upload",
                files={"file": ("reg.md", md, "text/markdown")},
                headers=headers,
            )
            body2 = resp2.json()
            assert body2["status"] == "ready"
            assert body2["unchanged"] is True
        finally:
            vs.VectorStore.replace_document = orig


def test_jobs_list_endpoint() -> None:
    """GET /jobs (terproteksi) menampilkan riwayat job ingestion."""
    with TestClient(app) as client:
        headers = _auth(client)
        data = client.get("/jobs", headers=headers).json()
        assert data["status"] == "ok"
        assert isinstance(data["jobs"], list)
