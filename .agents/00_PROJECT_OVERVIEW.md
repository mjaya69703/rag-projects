# 00 — Project Overview

## Apa ini
**Personal AI Knowledge Base (RAG)** — sistem tanya-jawab dari dokumen pribadi (PDF, MD, TXT, DOCX, PPTX, HTML, URL). Embedding lokal (MiniLM), LLM API eksternal, dioptimasi untuk environment terbatas (LXC 2-3GB RAM). Bahasa: Indonesia + Inggris.

## Status sprint (per 07-08-2026)
| Sprint | Fokus | Status |
|--------|-------|--------|
| 1 | Ingestion (PyMuPDF + docx/pptx + chunking + ChromaDB) | ✅ |
| 2 | Query & LLM (RAG engine + hybrid search BM25) | ✅ |
| 3 | Semantic Cache Aware Filter & Relevance Floor | ✅ |
| 4 | FastAPI Backend (+ session management API + SQLite) | ✅ |
| 5 | Custom Frontend (SPA React 19 + Vite + Bun, disajikan FastAPI) | ✅ |
| 6 | Deployment & Security (Cloudflare Tunnel) | 🔶 artefak siap di `deploy/`, deploy nyata menyusul |
| 7 | Learning loop (15 fitur), custom modals 100%, loading indicators | ✅ selesai 100% |

## Fitur Utama Sistem
- **Multi-Format Ingest**: PDF, MD, TXT, DOCX, PPTX, HTML, URL, & Watch-Folder auto-index (`uploads/`).
- **Hybrid Search**: BM25 keyword matching + ChromaDB vector similarity.
- **RAG Engine + SSE Streaming**: Jawaban cepat dengan rujukan sumber (file, halaman, heading).
- **Semantic Cache & Relevance Floor**: Menolak menjawab jika materi tidak relevan (`RAG_MIN_SIMILARITY`).
- **React 19 SPA Frontend**: Modern OKLCH Glassmorphism, 100% custom React modals (`ConfirmDialog`, `PromptDialog`), serta indikator loading & spinner visual.
- **15 Fitur Learning Loop**:
  - Library Dokumen & Chunk Inspector (dengan catatan anotasi)
  - Quiz Generator Interaktif (opsi A/B/C/D, koreksi + penjelasan LLM, riwayat skor)
  - Flashcards 3D (3D card flip, mastery progress, navigasi keyboard)
  - Progress Analytics Dashboard (KPI stat, cakupan dokumen per bab, weak spot matrix)
  - Spaced Repetition Review queue & Termometer pertanyaan berulang
- **Access Layers**: MCP Server (`python -m app.mcp_server`) & Bot Telegram (`python -m app.telegram_bot`).

## Environment
- OS dev: **Windows** (powershell/cmd). Target deploy: Ubuntu/Debian LXC.
- Python 3.13 backend, Bun untuk frontend React build (`bun run build`).
