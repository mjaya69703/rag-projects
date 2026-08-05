"""Smoke test untuk frontend custom yang disajikan oleh FastAPI."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["PERSIST_DIR"] = str(Path(_TMP) / "chroma")
os.environ["UPLOAD_DIR"] = str(Path(_TMP) / "uploads")
os.environ["DB_PATH"] = str(Path(_TMP) / "chat.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_shell_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Knowledge Base" in response.text
        assert 'src="/app.js?v=5"' in response.text
        assert 'href="/styles.css?v=6"' in response.text
        assert "dompurify" in response.text.lower(), "DOMPurify harus disertakan (sanitasi XSS)"
        assert 'id="stop-button"' in response.text, "tombol batal streaming harus ada"
        assert client.get("/tokens.css").status_code == 200
        assert client.get("/styles.css").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert client.get("/health").json() == {"status": "ok"}
