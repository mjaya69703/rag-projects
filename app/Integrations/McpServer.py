"""Model Context Protocol (MCP) Server integration."""

from __future__ import annotations

import logging
import threading
from typing import Any, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
    _MCP_AVAILABLE = True
except ImportError:
    FastMCP = None
    _MCP_AVAILABLE = False

from app.Core.Config import Settings, config
from app.Repositories.VectorRepository import VectorRepository
from app.Services.RagService import RagService, Source

logger = logging.getLogger(__name__)
SERVER_NAME = "rag-knowledge-base"

_engine: RagService | None = None
_engine_lock = threading.Lock()


def create_engine() -> RagService:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                settings = Settings()
                settings.upload_dir.mkdir(parents=True, exist_ok=True)
                store = VectorRepository(persist_dir=settings.persist_dir)
                _engine = RagService(vector_repo=store)
    return _engine


def format_sources(sources: list[Source]) -> str:
    if not sources:
        return ""
    lines = ["\n\nSumber:"]
    for s in sources:
        lines.append(f"- {s.source} (hal. {s.page}) — {s.heading}")
    return "\n".join(lines)


def build_mcp_server() -> Any:
    if not _MCP_AVAILABLE:
        raise RuntimeError("mcp package is not installed.")
    mcp = FastMCP(SERVER_NAME)

    @mcp.tool()
    def query(question: str, top_k: int = 5) -> str:
        """Jawab pertanyaan berdasarkan dokumen di knowledge base."""
        engine = create_engine()
        ans = engine.query(question=question, top_k=top_k)
        return ans.answer + format_sources(ans.sources)

    @mcp.tool()
    def list_documents() -> list[str]:
        """Daftar nama dokumen yang sudah terindeks di knowledge base."""
        engine = create_engine()
        return engine.vector_repo.list_all_documents()

    @mcp.tool()
    def find_locations(question: str, top_k: int = 15) -> list[dict]:
        """Cari lokasi (dokumen, halaman, heading) yang membahas topik tertentu."""
        engine = create_engine()
        return engine.find_locations(question, top_k=top_k)

    return mcp
