"""Smoke test integrasi eksternal: MCP server & Telegram bot.

Fokus: keduanya bisa di-build dan handler/tools terdaftar dengan benar
setelah refactor ke arsitektur layer (tanpa perlu koneksi jaringan).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.Integrations.McpServer import _MCP_AVAILABLE, build_mcp_server, format_sources
from app.Integrations.TelegramBot import (
    _PTB_AVAILABLE,
    build_telegram_app,
)
from app.Services.RagService import Source


def test_mcp_server_tools_registered() -> None:
    """build_mcp_server() sukses & tool inti terdaftar."""
    if not _MCP_AVAILABLE:
        import pytest

        pytest.skip("paket mcp tidak terinstall")
    mcp = build_mcp_server()
    manager = getattr(mcp, "_tool_manager", None)
    tools = getattr(manager, "_tools", None) if manager else None
    if tools is None:
        # API internal FastMCP tidak stabil antar versi — minimal pastikan
        # dekorator & atribut dasar ada supaya server bisa dijalankan.
        assert hasattr(mcp, "tool")
        return
    names = {t.name for t in tools.values()}
    assert {"query", "list_documents", "find_locations"} <= names, names


def test_mcp_format_sources() -> None:
    src = Source(source="materi.pdf", page=2, heading="VLAN", text="x", distance=0.1, chunk_index=0)
    text = format_sources([src])
    assert "materi.pdf" in text
    assert "VLAN" in text


def test_telegram_bot_builds_handlers() -> None:
    """build_telegram_app() tanpa jaringan: handler command & message terdaftar."""
    if not _PTB_AVAILABLE:
        import pytest

        pytest.skip("python-telegram-bot tidak terinstall")
    app = build_telegram_app("123456:fake-token", engine=None, settings=None)
    handlers = app.handlers[0] if app.handlers else []
    kinds = {type(h).__name__ for h in handlers}
    assert "CommandHandler" in kinds, f"harus ada command handler: {kinds}"
    assert "MessageHandler" in kinds, f"harus ada message handler: {kinds}"
