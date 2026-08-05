# 05 — Testing & Run

## Menjalankan semua test
```cmd
.venv\Scripts\python -m pytest tests\ -q
```
Status saat handover: **33 passed** (06-08-2026, 1 warning StarletteDeprecation tidak fatal; sebelumnya 27 passed).

| File test | Cakupan |
|-----------|---------|
| `test_pipeline.py` | parse PDF → chunk → simpan → search (Sprint 1) |
| `test_rag.py` | RAG engine + LLM mock + error handling (Sprint 2) |
| `test_cache.py` | semantic cache: hit, parafrase, anti-false-positive, persistent, eviction, **isolasi filter dokumen** (06-08-2026) |
| `test_api.py` | FastAPI: upload/query/documents/delete + session CRUD & history + **validasi PDF palsu, rate limit 429, CORS** (06-08-2026) |
| `test_db.py` | SQLite sessions/messages/summaries/cascade (Sprint 4) |
| `test_frontend.py` | Smoke test SPA statis: shell tersaji, assets OK (Sprint 5; menggantikan `test_ui.py` Streamlit) |
| `benchmark_embedding.py` | (non-test) benchmark MiniLM vs e5-small |
| `diagnose_retrieval.py` | (non-test) diagnosa retrieval query-vs-dokumen |

Test API menggunakan TestClient in-process dengan env PERSIST_DIR/UPLOAD_DIR
diarahkan ke temp dir. **Tidak perlu server berjalan.**

## Menjalankan aplikasi
```cmd
rem Satu proses saja — FastAPI menyajikan API + SPA statis
.venv\Scripts\python -m uvicorn app.main:app --port 8000
rem atau: start.cmd / npm run dev (launcher dengan watchdog & kill-tree)
```

## CLI
```cmd
.venv\Scripts\python ingest.py uploads\file.pdf --source "Nama" --replace
.venv\Scripts\python ask.py "pertanyaan" -k 5
.venv\Scripts\python query.py "kata kunci" -k 5
```

## LARANGAN
- Jangan commit `.env`, `.venv`, `data/`, `uploads/`, `*.db`, `__pycache__`.
