"""Smoke test access layer: MCP server & Telegram bot.

Library mcp / python-telegram-bot belum tentu terinstall (integrator yang
install) — auto-skip via importorskip. Ini test ringan, bukan integration:
hanya cek tool terdaftar & bot terbangun tanpa error.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp")
pytest.importorskip("telegram")

from app import mcp_server, telegram_bot  # noqa: E402


def _tool_names(server) -> set[str]:
    """Nama tool terdaftar di FastMCP — kompatibel lintas versi SDK."""
    manager = getattr(server, "_tool_manager", None)
    if manager is not None and hasattr(manager, "list_tools"):
        return {t.name for t in manager.list_tools()}
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict):
        return set(tools)
    raise AssertionError(
        "Struktur internal FastMCP tidak dikenali — cek versi SDK mcp"
    )


def test_mcp_tools_registered() -> None:
    """Semua tool terdaftar di FastMCP tanpa menjalankan server."""
    server = mcp_server.create_server()
    names = _tool_names(server)
    expected = {"query", "list_documents", "find_locations", "repeated_questions"}
    assert expected <= names, f"Tool kurang: {expected - names}"
    assert server.name == "rag-knowledge-base"


def test_telegram_bot_builds_with_token() -> None:
    """Application bot terbangun tanpa error saat token diberikan."""
    application = telegram_bot.build_application(token="12345:test-token")
    assert application is not None


def test_telegram_main_exits_zero_without_token(monkeypatch) -> None:
    """Tanpa TELEGRAM_BOT_TOKEN, main() exit 0 (bukan error)."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert telegram_bot.main() == 0
