"""Core configuration module for the application."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MAX_UPLOAD_MB: int = 50
SLIDING_WINDOW_DEFAULT: int = 15   # Mode 1: last N messages
SUMMARY_RECENT: int = 5            # Mode 2: summary + last 5 messages
SUMMARY_INTERVAL: int = 10         # auto-generate summary every 10 messages
TOKEN_WARNING: int = 4000          # token warning threshold

PUBLIC_API_PATHS: set[str] = {"/health"}

DEFAULT_REDACTION_PATTERNS: list[str] = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"(\+?62|0)8[0-9]{7,12}",
    r"(sk-[A-Za-z0-9]{20,}|[A-Za-z0-9_-]{32,})",
]

DEFAULT_CORS_ORIGINS: str = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8000,http://127.0.0.1:8000"
)


def _parse_origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"} if raw else default


def _parse_int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _derive_provider_label(api_base: str) -> str:
    if not api_base:
        return "provider LLM eksternal"
    from urllib.parse import urlparse
    host = urlparse(api_base).hostname or api_base
    return f"provider LLM eksternal ({host})"


CORS_ORIGINS = _parse_origins(os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS))


class Settings:
    """Application Settings Provider."""

    def __init__(self) -> None:
        self.persist_dir = os.getenv("PERSIST_DIR", "data/chroma_db")
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
        self.db_path = os.getenv("DB_PATH", "data/chat.db")
        self.log_dir = os.getenv("LOG_DIR", "")
        self.cors_origins = list(CORS_ORIGINS)
        self.rate_limit_qpm = int(os.getenv("RATE_LIMIT_QPM", "30"))
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.api_token = os.getenv("API_TOKEN", "").strip()

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
        self.retain_chat_days = _parse_int(os.getenv("RETAIN_CHAT_DAYS"), 0)
        self.cache_max_days = _parse_int(os.getenv("CACHE_MAX_DAYS"), 0)
        self.staging_dir = self.upload_dir / ".staging"


config = Settings()
