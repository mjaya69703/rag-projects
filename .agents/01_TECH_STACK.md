# 01 — Tech Stack & Keputusan Teknis

## Stack aktif (yang benar-benar dipakai)
| Layer | Teknologi | Catatan |
|-------|-----------|---------|
| Backend | FastAPI + uvicorn | `app/main.py`, lifespan pattern, `app/config.py` (baca env) |
| Frontend | Custom SPA statis | `app/static/` (index.html, tokens.css, styles.css, app.js), disajikan FastAPI sejak 03-08-2026 (Streamlit & Next.js sudah tidak dipakai) |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` | ~130MB; tolerant bahasa informal |
| Vector DB | ChromaDB (persistent) | `data/chroma_db`, metrik cosine, telemetry dimatikan |
| PDF Parser | PyMuPDF (fitz) | Teks + deteksi heading via ukuran font |
| Chunking | `langchain-text-splitters` RecursiveCharacterTextSplitter | chunk 500, overlap 50 |
| LLM | OpenAI-compatible endpoint **databyte AI** | `deepseek-v4-flash`, key di `.env` |
| Semantic cache | Implementasi sendiri di ChromaDB (collection `query_cache`) | GPTCache TIDAK dipakai (lihat 06) |
| Chat storage | SQLite (`data/chat.db`) | sessions, messages, summaries |
| HTTP client | httpx | Backend ke LLM & UI ke backend |

## Konfigurasi `.env`
```
LLM_API_KEY=...        # databyte AI key
LLM_API_BASE=https://ai.databyte.co.id/v1
LLM_MODEL=deepseek-v4-flash
PERSIST_DIR=data/chroma_db
UPLOAD_DIR=uploads
DB_PATH=data/chat.db   # tambahan Sprint 4
```
Opsional (06-08-2026): `RAG_MAX_TOKENS`, `CORS_ORIGINS`, `RATE_LIMIT_QPM`, `LOG_DIR` —
lengkap di `.env.example`.
`.env` TIDAK di-commit. Template: `.env.example`.

## Keputusan penting
1. **Python 3.14 + dependency versi terbaru** — versi yang di-pin di
   `docs/03_TECHNICAL_SPECIFICATION.md` (langchain 0.1.5, chromadb 0.4.22, dst.)
   tidak punya wheel cp314. Ini keputusan user (tanya dia sebelum mengubah).
   **Catatan 02-08-2026 (PC baru):** mesin ini cuma punya Python 3.13 — venv
   dibangun ulang dengan 3.13 (`py -3.13 -m venv`). Semua dep versi terbaru punya
   wheel cp313; pytest 26 passed.
2. **Torch CPU-only** saat install (`--index-url https://download.pytorch.org/whl/cpu`)
   — hemat bandwidth/disk.
3. **Embedding = MiniLM**, bukan e5-small (e5 di-revert — lihat 06).
4. **Top-K default 5**; pertanyaan luas ("isinya apa", "bikin soal") pakai `-k 10/15`.
5. **Cache threshold 0.25** (MiniLM); history chat non-empty → cache di-skip.
