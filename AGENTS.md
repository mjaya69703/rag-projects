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

## Arsitektur (keputusan penting):
- **`app/main.py` adalah SATU-SATUNYA router live** — semua endpoint API dan
  middleware (auth, rate-limit, logging) ada di sana.
- **Layer `app/Http/` (Controllers + Routes.py) BELUM di-mount** — jangan
  `include_router(api_router)` sembarangan: route-nya menduplikasi yang sudah
  ada di main.py (`/glossary`, `/learning/*`, `/annotations`) dan akan memicu
  konflik. Migrasikan per-domain lalu hapus duplikatnya dari main.py.
  Ada guard otomatis: `tests/test_api.py::test_http_layer_not_mounted`.
- **Fitur baru dikerjakan di jalur live** (main.py + `app/learning.py` dkk),
  bukan di layer Http. Service di `app/Services/` boleh dipakai ulang selama
  tidak membuat client ChromaDB kedua.

## Catatan Deploy:
- `.env` TIDAK ikut repo; buat dari `.env.example` (format yang dibaca code:
  `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`). Berlaku sama untuk Docker
  (`docker compose`) maupun non-Docker (`start.sh`).
- Reranker cross-encoder aktif via `RERANK_ENABLED` (default true; matikan
  dengan `0` di test/CI biar cepat).

*Jangan commit `.env` (API key LLM).*
