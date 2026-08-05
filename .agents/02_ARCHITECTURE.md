# 02 — Architecture & Struktur

## Struktur folder
```
rag-projects/
├── app/
│   ├── __init__.py
│   ├── pdf_parser.py     # PyMuPDF: extract_pages, parse_pdf, deteksi heading
│   ├── vector_store.py   # ChromaDB + MiniLM; add_documents/search/list/delete/reset/close
│   ├── llm_client.py     # OpenAI-compatible chat via httpx (LLMError)
│   ├── rag_engine.py     # RAGEngine.query(question, top_k, where, history)
│   ├── semantic_cache.py # SemanticCache (collection query_cache, threshold 0.25)
│   ├── db.py             # SQLite: sessions/messages/session_summaries
│   ├── config.py         # Baca env terpusat (Settings) — ditambahkan 06-08-2026
│   └── main.py           # FastAPI app + lifespan + endpoint + rate limit + CORS + serve SPA
├── tests/                # test_pipeline, test_rag, test_cache, test_api, test_db, test_frontend
├── uploads/              # PDF yang diindeks
├── data/                 # chroma_db/ + chat.db
├── docs/                 # dokumentasi spesifikasi
├── .agents/              # handover pack ini
├── app/static/           # Custom SPA (index.html, tokens.css, styles.css, app.js) — disajikan FastAPI di "/" (mount terakhir)
├── deploy/               # Artefak deployment LXC + Cloudflare Tunnel (06-08-2026)
├── ingest.py             # CLI index PDF
├── ask.py                # CLI tanya-jawab (RAG engine)
├── query.py              # CLI search chunk saja
├── requirements.txt
├── .env / .env.example
└── AGENTS.md             # pointer ke .agents/
```

## Alur ingestion
Upload (UI/CLI) → simpan PDF ke `uploads/` → `parse_pdf()` (extract per halaman,
deteksi heading font-size, merge segmen pendek, skip footer/digit) →
`VectorStore.add_documents()` (embed MiniLM → upsert ke ChromaDB, metadata
`{source, page, heading, chunk_index}`).

## Alur query
`RAGEngine.query()`: cek cache (jika tanpa history) → `VectorStore.search()` Top-K →
susun prompt `KONTEKS:[1..k]` + `PERTANYAAN` → `LLMClient.chat()` (max_tokens 512) →
simpan cache (jika statis) → `RAGAnswer(answer, sources, model, cached)`.

## Alur query ber-session (Sprint 4)
1. `_build_history()`: sliding (last N) atau summary (ringkasan + last 5)
2. Simpan pesan user ke SQLite
3. `engine.query(..., history=history)` → history masuk prompt, cache di-skip
4. Simpan jawaban + sources ke SQLite
5. `_post_query_tasks()`: auto-title (pesan pertama), auto-summary (tiap 10 pesan)

## Endpoint API (app/main.py)
- `POST /upload`, `POST /query`, `GET /documents`, `DELETE /documents/{source}`
- `POST /sessions/create`, `GET /sessions/list`, `GET /sessions/{id}/messages`,
  `PUT /sessions/{id}/rename`, `DELETE /sessions/{id}`
- `GET /health`

Semua response `{"status": "ok", ...}`; error via HTTPException (400/404/422/502).
