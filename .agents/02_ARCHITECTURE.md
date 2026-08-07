# 02 — Architecture & Struktur

## Struktur Proyek
```
rag-projects/
├── frontend/             # React 19 + Vite + React Router SPA (dikelola Bun)
│   ├── src/
│   │   ├── pages/        # Chat.tsx, Library.tsx, Quiz.tsx, Flashcards.tsx, Progress.tsx, Settings.tsx
│   │   ├── components/   # ConfirmDialog, PromptDialog, Dialog, Markdown, SourceCard, Toast, UploadDialog, Sidebar, PageHeader, Icon
│   │   ├── context/      # SessionsContext.tsx
│   │   └── styles/       # tokens.css, styles.css
│   ├── package.json
│   └── vite.config.ts    # OutDir: ../app/static, proxy API ke 127.0.0.1:8000
├── app/
│   ├── pdf_parser.py     # PyMuPDF: extract_pages, parse_pdf, deteksi heading
│   ├── md_parser.py      # Markdown parser
│   ├── office_parser.py  # docx, pptx, html parser
│   ├── url_parser.py     # Web scraper & url parser
│   ├── watch_folder.py   # Watch folder uploads/ auto-indexer
│   ├── vector_store.py   # ChromaDB + MiniLM
│   ├── hybrid_search.py  # BM25 + Vector hybrid search engine
│   ├── llm_client.py     # OpenAI-compatible chat via httpx
│   ├── rag_engine.py     # RAGEngine.query()
│   ├── semantic_cache.py # SemanticCache (collection query_cache)
│   ├── learning.py       # Spaced repetition, weak spots, quiz generator, flashcards
│   ├── annotations.py    # Chunk annotation notes manager
│   ├── db.py             # SQLite: sessions, messages, review_cards, quiz_history, annotations
│   ├── config.py         # Config Settings
│   ├── main.py           # FastAPI app + CORS + rate limit + serve SPA
│   ├── mcp_server.py     # Model Context Protocol (MCP) server
│   └── telegram_bot.py   # Bot Telegram integration
├── app/static/           # Hasil build React (bun run build dari frontend/)
├── deploy/               # Systemd unit & script LXC deployment
├── tests/                # Pytest unit tests (106 passed)
├── uploads/              # Folder watch-folder dokumen
├── data/                 # chroma_db/ & chat.db
├── ingest.py / ask.py    # CLI tools
└── start.cmd / run_dev.py# Dev process runner & watchdog
```

## Alur Ingestion & Query
- **Ingestion**: Upload (UI/CLI/Watch-folder/URL) → `parser` → `VectorStore.add_documents()` → MiniLM embedding → ChromaDB (`source`, `page`, `heading`, `chunk_index`).
- **Query**: `RAGEngine.query()` → Cek semantic cache → `HybridSearch` (BM25 + ChromaDB) → Prompt RAG → LLM API → Return `RAGAnswer` + `SourceRef`.
- **Query Stream SSE**: `/query/stream` melayani event `meta`, `delta` (text chunk), `done`, `error`.

## Single-Page Application (SPA) Routing
FastAPI menyajikan file statis dari `app/static/`. Semua request non-API secara otomatis dialihkan ke `app/static/index.html` (SPA fallback), sehingga halaman React Router (`/library`, `/quiz`, `/flashcards`, `/progress`, `/settings`) bekerja tanpa 404.
