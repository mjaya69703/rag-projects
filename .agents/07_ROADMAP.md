# 07 — Roadmap & Sisa Pekerjaan

## Fitur Selesai 100% (per 07-08-2026) ✅
- [x] Ingestion Multi-Format (PDF, MD, TXT, DOCX, PPTX, HTML, URL, Watch-Folder `uploads/`)
- [x] RAG Engine & Hybrid Search (BM25 + ChromaDB Vector cosine similarity MiniLM)
- [x] Semantic Cache Aware Filter & Relevance Floor (`RAG_MIN_SIMILARITY`)
- [x] FastAPI Backend & Session Management (SQLite persistent)
- [x] SPA React 19 + Vite + Bun disajikan langsung dari FastAPI (`app/static/`)
- [x] OKLCH Glassmorphism Design System (Dark/Light mode switcher)
- [x] 100% Custom React Modals (`ConfirmDialog`, `PromptDialog` — 0% browser default popups)
- [x] Indikator Loading & Spinners visual di seluruh aksi async
- [x] 15 Fitur Learning Loop:
  - Library & Interactive Chunk Inspector (dengan catatan anotasi)
  - Quiz Generator Interaktif (opsi A/B/C/D, koreksi + penjelasan LLM, riwayat skor)
  - Flashcards 3D (3D card flip, mastery progress, navigasi keyboard)
  - Progress Analytics Dashboard (KPI stat, cakupan dokumen per bab, weak spot matrix)
  - Spaced Repetition Review queue & Termometer pertanyaan berulang
- [x] Access Layers: MCP Server (`app/mcp_server`) & Bot Telegram (`app/telegram_bot`)

## Sprint 6: Deployment & Security (artefak di `deploy/` siap) 🔶
Goal: bisa diakses dari mana saja dengan aman via Cloudflare Tunnel.

Task tersisa (perlu akses user ke LXC & Cloudflare Dashboard):
- [ ] Install & configure `cloudflared` di LXC (token tunnel dari dashboard)
- [ ] Buat tunnel di Cloudflare Dashboard + public hostname
- [ ] Setup Cloudflare Access policy (email allowlist)
- [ ] Jalankan `install_lxc.sh`, isi `/opt/rag/.env`, verifikasi service
- [ ] Test akses dari external network

## Perbaikan dari Audit 2026-08-09 (in progress) 🔶

> Berdasar `.docs/PROJECT_AUDIT_2026-08-09.md` (temuan P0/P1/P2). Item di bawah **direncanakan/berjalan — detail belum tentu ada di kode**. Jangan berasumsi selesai sebelum cek kode & test.

- [ ] **P0-02 Auth token aplikasi** — status: in progress (2026-08-09).
- [ ] **P0-01 SSRF protection** pada ingest URL (blokir private/loopback/metadata IP, validasi redirect & ukuran response) — status: in progress (2026-08-09).
- [ ] **P1-01 Ingestion async + atomic** (job queue, staging, swap atomik, cancel/progress) — status: in progress (2026-08-09).
- [ ] **P2-08 Backup/restore & recovery** (SQLite + uploads + index metadata, migration/version manifest) — status: in progress (2026-08-09).
- [ ] **P2-04 Quiz attempt server-side** + scoring deterministik (answer key di server, LLM hanya untuk penjelasan) — status: in progress (2026-08-09).
- [ ] P0-03 privacy disclosure/retention, P1-02 document registry, P1-03 prompt injection, P1-04 relevance/reranker, P2-03 spaced repetition kaya, P2-05 observability — belum dimulai.
