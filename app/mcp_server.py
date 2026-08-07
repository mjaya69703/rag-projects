"""MCP server: expose knowledge base sebagai tools untuk AI lain (stdio).

Tools:
- query: jawab pertanyaan + sumber (file/halaman/heading)
- list_documents: daftar dokumen terindeks
- find_locations: "di mana X dibahas" (group per file/halaman/heading)
- repeated_questions: termometer pertanyaan berulang

Jalankan: .venv\\Scripts\\python -m app.mcp_server
"""

from __future__ import annotations

import logging
import threading

try:
    from mcp.server.fastmcp import FastMCP

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover - tergantung env mesin
    FastMCP = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False

from app import db
from app.config import Settings
from app.rag_engine import RAGEngine, Source
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

SERVER_NAME = "rag-knowledge-base"

# --- Engine lazy singleton -------------------------------------------------
# Embedding model di VectorStore baru di-load saat query pertama, jadi
# import modul ini tidak menghabiskan RAM. Engine dibuat sekali dan dipakai
# bersama oleh semua tool (dan oleh telegram_bot via create_engine()).
_engine: RAGEngine | None = None
_engine_lock = threading.Lock()


def create_engine() -> RAGEngine:
    """Bangun (atau ambil) instance RAGEngine — lazy singleton.

    Bisa dipakai ulang oleh modul lain (mis. telegram_bot) supaya logika
    pembuatan engine tidak terduplikasi.
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                settings = Settings()
                settings.upload_dir.mkdir(parents=True, exist_ok=True)
                store = VectorStore(persist_dir=settings.persist_dir)
                _engine = RAGEngine(store=store)
                logger.info("RAGEngine dibuat: persist=%s", settings.persist_dir)
    return _engine


def format_sources(sources: list[Source]) -> str:
    """Format daftar sumber jadi teks ringkas (file/halaman/heading)."""
    lines: list[str] = []
    seen: set[tuple[str, int | None, str]] = set()
    for src in sources:
        key = (src.source, src.page, src.heading)
        if key in seen:
            continue
        seen.add(key)
        parts = [src.source]
        if src.page is not None:
            parts.append(f"halaman {src.page}")
        if src.heading:
            parts.append(f"bagian: {src.heading}")
        lines.append(f"- {', '.join(parts)}")
    return "\n".join(lines)


def _require_mcp() -> None:
    """SystemExit dengan instruksi bila SDK mcp belum terinstall."""
    if not _MCP_AVAILABLE:
        raise SystemExit("mcp belum terinstall — jalankan: pip install mcp")


def create_server() -> FastMCP:
    """Bangun FastMCP server dengan semua tool terdaftar (belum dijalankan)."""
    _require_mcp()
    server = FastMCP(SERVER_NAME)

    @server.tool()
    def query(question: str, top_k: int = 5, source: str | None = None) -> str:
        """Jawab pertanyaan berdasarkan dokumen terindeks, dengan sumber."""
        engine = create_engine()
        where = {"source": source} if source else None
        answer = engine.query(question, top_k=top_k, where=where)
        text = answer.answer
        if answer.sources:
            text += f"\n\nSumber:\n{format_sources(answer.sources)}"
        return text

    @server.tool()
    def list_documents() -> str:
        """Daftar dokumen terindeks (jumlah chunk & halaman)."""
        docs = create_engine().store.list_documents()
        if not docs:
            return "Belum ada dokumen terindeks."
        lines = [
            f"- {d['source']} — {d['chunks']} chunk, "
            f"halaman: {', '.join(map(str, d['pages'])) or '-'}"
            for d in docs
        ]
        return "Dokumen terindeks:\n" + "\n".join(lines)

    @server.tool()
    def find_locations(question: str) -> str:
        """Cari di dokumen mana topik pertanyaan dibahas (group per sumber)."""
        results = create_engine().store.search(question, top_k=15)
        if not results:
            return f"Tidak ada dokumen terindeks yang membahas: {question}"
        groups: dict[tuple[str, int | None, str], list[float]] = {}
        for r in results:
            meta = r["metadata"]
            key = (
                meta.get("source", "?"),
                meta.get("page"),
                meta.get("heading", ""),
            )
            groups.setdefault(key, []).append(r["distance"])
        lines: list[str] = []
        for (source, page, heading), dists in sorted(
            groups.items(), key=lambda kv: min(kv[1])
        ):
            page_s = f"halaman {page}" if page is not None else "tanpa halaman"
            heading_s = f", bagian: {heading}" if heading else ""
            lines.append(
                f"- {source} ({page_s}{heading_s}) — {len(dists)} chunk, "
                f"relevansi {min(dists):.3f}"
            )
        return "Topik ini dibahas di:\n" + "\n".join(lines)

    @server.tool()
    def repeated_questions(days: int = 7, min_hits: int = 2) -> str:
        """Termometer: pertanyaan yang diajukan berulang dalam N hari."""
        settings = Settings()
        try:
            db.init_db(settings.db_path)
            usage = db.usage_summary(settings.db_path, days=days)
            questions = db.repeated_questions(
                settings.db_path, days=days, min_hits=min_hits
            )
        except Exception as exc:
            logger.warning("repeated_questions gagal: %s", exc)
            return f"Gagal membaca database chat: {exc}"
        lines = [
            f"Pemakaian {days} hari terakhir: {usage['questions']} pertanyaan "
            f"dari {usage['sessions_active']} sesi aktif."
        ]
        if not questions:
            lines.append("Tidak ada pertanyaan berulang pada periode ini.")
        else:
            lines.append(f"{len(questions)} pertanyaan diulang >= {min_hits} kali:")
            for q in questions:
                lines.append(
                    f"- ({q['count']}x, terakhir {q['last_asked'][:10]}) "
                    f"{q['question'][:120]}"
                )
        return "\n".join(lines)

    return server


def main() -> int:
    """Entry point: jalankan server MCP via stdio."""
    _require_mcp()
    server = create_server()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
