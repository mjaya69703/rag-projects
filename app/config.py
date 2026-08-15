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

# Jalur yang boleh diakses TANPA token saat API_TOKEN diset.
# /health dibutuhkan systemd; SPA statis dilayani oleh spa_fallback.
PUBLIC_API_PATHS = {"/health"}

# Pola redaksi default (regex, diterapkan bila REDACTION_ENABLED=1):
# email, nomor telepon umum, dan pola mirip API key.
DEFAULT_REDACTION_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"(\+?62|0)8[0-9]{7,12}",
    r"(sk-[A-Za-z0-9]{20,}|[A-Za-z0-9_-]{32,})",
]

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8000,http://127.0.0.1:8000"
)


def _parse_origins(raw: str) -> list[str]:
    """Pisah daftar origin (dipisah koma), buang item kosong."""
    return [o.strip() for o in raw.split(",") if o.strip()]


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"} if raw else default


def _parse_int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


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

        # --- Keamanan aplikasi (P0-02) ---------------------------------
        # API_TOKEN diisi -> SEMUA endpoint API (kecuali /health & SPA)
        # wajib mengirim `Authorization: Bearer <token>` (fail-closed).
        self.api_token = os.getenv("API_TOKEN", "").strip()

        # --- Privasi & retensi (P0-03) ---------------------------------
        # Label provider LLM untuk disclosure. Default: hostname dari
        # LLM_API_BASE (jika ada) supaya user tahu data pergi ke mana.
        base = os.getenv("LLM_API_BASE", "").strip()
        self.llm_provider_label = os.getenv(
            "LLM_PROVIDER_LABEL", _derive_provider_label(base)
        )
        self.redaction_enabled = _parse_bool(
            os.getenv("REDACTION_ENABLED"), default=False
        )
        raw_patterns = os.getenv("REDACTION_PATTERNS", "")
        self.redaction_patterns = (
            [p.strip() for p in raw_patterns.split(",") if p.strip()]
            if raw_patterns.strip()
            else list(DEFAULT_REDACTION_PATTERNS)
        )
        # Retensi: 0 = simpan selamanya. >0 = purge otomatis saat start.
        self.retain_chat_days = _parse_int(os.getenv("RETAIN_CHAT_DAYS"), 0)
        self.cache_max_days = _parse_int(os.getenv("CACHE_MAX_DAYS"), 0)

        # Staging untuk upload asinkron (dibersihkan otomatis setelah
        # ingest selesai/gagal; tidak pernah di-scan watch-folder).
        self.staging_dir = self.upload_dir / ".staging"


def _derive_provider_label(api_base: str) -> str:
    """Label default provider LLM dari base URL (untuk disclosure privasi)."""
    if not api_base:
        return "provider LLM eksternal"
    from urllib.parse import urlparse

    host = urlparse(api_base).hostname or api_base
    return f"provider LLM eksternal ({host})"
