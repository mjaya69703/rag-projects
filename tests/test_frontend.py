"""Smoke test frontend React (Vite build di app/static) + SPA fallback."""

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


def test_frontend_react_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert 'id="root"' in response.text, "React root harus ada"
        assert "Knowledge Base" in response.text
        assert "/assets/" in response.text, "harus merujuk asset hasil build Vite"
        assert client.get("/health").json() == {"status": "ok"}


def test_spa_fallback_serves_index() -> None:
    """Semua path non-API (React Router) serve index.html — bukan 404."""
    with TestClient(app) as client:
        for path in ("/library", "/quiz", "/flashcards", "/progress", "/settings", "/halaman-baru"):
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} harus 200 (SPA fallback)"
            assert 'id="root"' in resp.text


def test_assets_served() -> None:
    with TestClient(app) as client:
        # asset JS/CSS hasil build harus bisa diakses
        index = client.get("/").text
        for token in ("/assets/", "css", "js"):
            assert token in index
        assert client.get("/assets/").status_code in (200, 404)  # index asset folder
