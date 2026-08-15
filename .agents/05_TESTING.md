# 05 — Testing & Run

> ⚠️ **Catatan verifikasi (2026-08-09, audit `.docs/PROJECT_AUDIT_2026-08-09.md`):** angka "106 passed" di bawah adalah hasil di mesin dev (07-08-2026) dan **belum terverifikasi ulang penuh** di environment audit — subset parser/database/ingestion lulus (47 pass), tapi suite API gagal di audit karena model embedding mencoba akses Hugging Face, dan `bun run build` gagal karena EPERM pada `frontend/node_modules/picomatch/index.js`. Jangan mengklaim "semua test pass" tanpa menjalankannya sendiri.

## Menjalankan Backend Unit Tests
```cmd
.venv\Scripts\python -m pytest tests\ -q
```
Status saat ini: **106 passed** (07-08-2026).

| File test | Cakupan |
|-----------|---------|
| `test_pipeline.py` | parse PDF → chunk → simpan → search |
| `test_rag.py` | RAG engine + LLM mock + error handling + hybrid search |
| `test_cache.py` | semantic cache: hit, parafrase, anti-false-positive, persistent, eviction, isolasi filter dokumen |
| `test_api.py` | FastAPI: upload/query/documents/delete + session CRUD & history + validasi PDF, rate limit, CORS |
| `test_db.py` | SQLite sessions, messages, review_cards, quiz_history, annotations, weak_spots |
| `test_frontend.py` | Smoke test SPA React: shell tersaji di `/`, static assets |

## Menjalankan Build & Verification Frontend
```cmd
cd frontend
bun run build
```
*Memastikan seluruh komponen React, TypeScript type-check, dan bundling Vite sukses tanpa error.*

## Menjalankan Aplikasi Web
```cmd
start.cmd
```
*(atau via python: `.venv\Scripts\python run_dev.py`)*

- Buka **UI + API** di `http://127.0.0.1:8000`.

## CLI Tools
```cmd
.venv\Scripts\python ingest.py uploads\file.pdf --source "Nama" --replace
.venv\Scripts\python ask.py "pertanyaan" -k 5
.venv\Scripts\python query.py "kata kunci" -k 5
```
