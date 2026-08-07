"""Konfigurasi aplikasi dari environment (file .env).

Semua setting yang dibaca dari env dikumpulkan di sini supaya mudah
ditelusuri dan diuji (test me-set env SEBELUM import app.main).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Baca .env persis satu kali (main.py tidak memanggil load_dotenv lagi).
load_dotenv()

MAX_UPLOAD_MB = 50
SLIDING_WINDOW_DEFAULT = 15   # Mode 1: ambil last N pesan
SUMMARY_RECENT = 5            # Mode 2: summary + last 5 pesan
SUMMARY_INTERVAL = 10         # auto-generate summary tiap 10 pesan
TOKEN_WARNING = 4000          # peringatan token per session

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8000,http://127.0.0.1:8000"
)


def _parse_origins(raw: str) -> list[str]:
    """Pisah daftar origin (dipisah koma), buang item kosong."""
    return [o.strip() for o in raw.split(",") if o.strip()]


# Dibaca saat import supaya middleware CORS (module-level) bisa memakainya.
CORS_ORIGINS = _parse_origins(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS))


class Settings:
    def __init__(self) -> None:
        self.persist_dir = os.getenv("PERSIST_DIR", "data/chroma_db")
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
        self.db_path = os.getenv("DB_PATH", "data/chat.db")
        self.log_dir = os.getenv("LOG_DIR", "")  # kosong = file logging NONAKTIF
        self.cors_origins = list(CORS_ORIGINS)
        self.rate_limit_qpm = int(os.getenv("RATE_LIMIT_QPM", "30"))  # 0 = nonaktif
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
