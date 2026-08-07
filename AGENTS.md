# AGENTS.md

Handover pack untuk agent AI yang akan meneruskan proyek RAG ini.

**Dokumentasi Lengkap:** [`.agents/README.md`](.agents/README.md) (baca file 00–08).

## Status Terkini (07-08-2026)
- **Frontend SPA**: React 19 + Vite + React Router (dikelola **Bun**). Di-build dari `frontend/` ke `app/static/` via `bun run build`.
- **UI Design System**: OKLCH Dark/Light Glassmorphism, 100% custom React modals (`ConfirmDialog`, `PromptDialog`), serta indikator loading & spinner visual di semua aksi async.
- **Backend & Feature Ecosystem**: FastAPI, ChromaDB + MiniLM, Hybrid Search (BM25 + Vector), Ingestion (PDF, MD, TXT, DOCX, PPTX, HTML, URL, Watch-folder), 15 Fitur Learning Loop (Quiz, Flashcards 3D, Progress Analytics, Spaced Repetition, Weak-spots), MCP Server, & Bot Telegram.

## Perintah Penting:
- **Run App**: `start.cmd`
- **Build Frontend**: `cd frontend && bun run build`
- **Run Backend Tests**: `.venv\Scripts\python -m pytest tests\ -q`

*Jangan commit `.env` (API key LLM).*
