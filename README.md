# Personal AI Knowledge Base (RAG)

Sistem *Retrieval-Augmented Generation* (RAG) pribadi: upload PDF → tanya-jawab dengan AI berdasarkan isi dokumen, hemat token via semantic cache. Dioptimasi untuk berjalan di environment terbatas (LXC RAM 2-3GB) dengan embedding model lokal + LLM API eksternal.

---

## 📊 Status Pengembangan (terakhir update: 06-08-2026)

| Sprint | Fokus | Status |
|--------|-------|--------|
| 1 | PDF Ingestion (parser + ChromaDB) | ✅ |
| 2 | Query & LLM Integration (RAG engine) | ✅ |
| 3 | Semantic Cache | ✅ |
| 4 | FastAPI Backend (+ session management API) | ✅ |
| 5 | Custom Frontend (SPA statis, disajikan FastAPI) | ✅ |
| 6 | Deployment & Security (Cloudflare) | 🔶 artefak siap (`deploy/`), deploy nyata menyusul |

> **Catatan:** Frontend aktual adalah **SPA statis** (`app/static/`) yang disajikan langsung oleh FastAPI
> di `http://127.0.0.1:8000` — **bukan** Next.js dan **bukan** Streamlit (keduanya sudah tidak dipakai;
> lihat `.agents/` untuk riwayat). Tidak ada server frontend terpisah.

## 💬 Fitur Utama

- Upload PDF → smart chunking berbasis heading → embedding lokal (MiniLM) → ChromaDB
- Tanya-jawab dengan source citation (file, halaman, bagian) — markdown + code highlighting
- **Streaming jawaban via SSE** (`/query/stream`) — persepsi latency hilang
- Semantic cache (pertanyaan identik/parafrase → tanpa call LLM), **aware filter dokumen**
- Multi-session chat persistent (SQLite): sliding window / summary mode, auto-title, auto-summary
- UI: sidebar session/dokumen, command palette (`Ctrl/Cmd+K`), dark/light theme, dokumen filter, top-k
- Rate limiting per-IP, CORS terkontrol, log ke file (opsional)

## 🚀 Cara Pakai

### Setup Awal
```cmd
rem 1. Setup Python venv backend (Python 3.13)
py -3.13 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   rem isi LLM_API_KEY / LLM_API_BASE / LLM_MODEL
```

### Menjalankan Sistem (1 Perintah)
```cmd
start.cmd
```
*(atau via npm: `npm run dev` / python: `.venv\Scripts\python run_dev.py`)*

- Buka **UI + API** di `http://127.0.0.1:8000` — FastAPI menyajikan SPA sekaligus API
- `run_dev.py` punya watchdog: restart otomatis jika backend crash (maks 4x gagal cepat) dan
  peringatan RAM bila pohon proses melewati `RAG_BACKEND_RAM_LIMIT_MB` (default 2048)

## 🧪 Testing

```cmd
rem Jalankan backend unit test suite (pytest)
.venv\Scripts\python -m pytest tests\ -q

rem Lint (ruff)
.venv\Scripts\python -m ruff check .
```

## 📁 Struktur Proyek

- `app/` — backend FastAPI: `pdf_parser`, `vector_store`, `llm_client`, `rag_engine`,
  `semantic_cache`, `db` (SQLite sessions), `config` (baca env), `main` (API + CORS + rate limit)
- `app/static/` — frontend SPA custom (index.html, tokens.css, styles.css, app.js) disajikan FastAPI
- `deploy/` — artefak deployment LXC + Cloudflare Tunnel (systemd unit, script install, panduan)
- `tests/` — unit & pipeline test (pytest) + benchmark/diagnostic scripts
- `uploads/` — PDF yang diindeks
- `data/` — ChromaDB (vektor + query cache) & `chat.db` (session history)
- `docs/` & `.agents/` — dokumentasi spesifikasi dan handover pack
- `ingest.py` / `ask.py` / `query.py` — CLI untuk ingestion dan query tanpa UI

## 🔒 Keamanan

- Konfigurasi LLM (API key) disimpan di `.env` — **jangan commit ke git**
- Template tersedia di `.env.example`
- CORS origin eksplisit via `CORS_ORIGINS`; rate limit via `RATE_LIMIT_QPM`
- Deployment aman: bind `127.0.0.1` + Cloudflare Tunnel + Cloudflare Access (lihat `deploy/README-DEPLOY.md`)
