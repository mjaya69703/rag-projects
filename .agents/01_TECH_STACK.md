# 01 — Tech Stack & Keputusan Teknis

## Stack Aktif (Yang Beneran Dipakai)

| Layer | Teknologi | Catatan |
|-------|-----------|---------|
| Backend | FastAPI + uvicorn | `app/main.py`, lifespan pattern, `app/config.py` (baca env) |
| Frontend | React 19 + Vite + React Router | Folder `frontend/`, di-build dengan **Bun** (`bun run build`) ke `app/static/` |
| Styling | Vanilla CSS (OKLCH Tokens + Glassmorphism) | `tokens.css` & `styles.css`, responsive, 3D card perspective |
| Custom UI Modals | `<ConfirmDialog>` & `<PromptDialog>` | 100% custom React modals (tanpa modal bawaan browser `confirm/prompt`) |
| Loading UI | `.spinner` ring & `.typing-dots` | Indikator visual loading di semua aksi async (quiz grading, chunk preview, upload, dll) |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` | ~130MB; tolerant bahasa informal |
| Vector DB | ChromaDB (persistent) | `data/chroma_db`, metrik cosine, telemetry dimatikan |
| Hybrid Search | BM25 + Vector | Combined keyword & semantic search |
| Parsers | PyMuPDF (PDF), docx, pptx, bs4 (HTML), markdown | Smart chunking berbasis heading font-size |
| LLM | OpenAI-compatible endpoint **databyte AI** | `deepseek-v4-flash`, key di `.env` |
| Semantic cache | Implementasi sendiri di ChromaDB (collection `query_cache`) | Aware filter dokumen & relevance floor |
| Chat & Learning DB | SQLite (`data/chat.db`) | sessions, messages, review_cards, quiz_history, annotations, weak_spots |
| HTTP client | httpx | Backend ke LLM & UI API client |
| Package Manager Frontend | **Bun** | Wajib pakai `bun install` & `bun run build` di folder `frontend/` |

## Konfigurasi `.env`
```ini
LLM_API_KEY=...        # databyte AI key
LLM_API_BASE=https://ai.databyte.co.id/v1
LLM_MODEL=deepseek-v4-flash
PERSIST_DIR=data/chroma_db
UPLOAD_DIR=uploads
DB_PATH=data/chat.db
RAG_MIN_SIMILARITY=0.6
```

## Perintah Build & Run Utama
```cmd
rem Build frontend SPA (React + Vite via Bun):
cd frontend && bun run build

rem Run backend (FastAPI):
.venv\Scripts\python run_dev.py
```
