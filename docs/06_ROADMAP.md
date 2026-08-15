# Roadmap

> **Status 07-08-2026:** Sprint 1–5 & 7 selesai 100%. Frontend menggunakan **React 19 + Vite + React Router (dikelola Bun)** yang disajikan FastAPI dari `app/static/`. UI menggunakan 100% Custom React Modals (`ConfirmDialog`, `PromptDialog`), indikator loading & spinner visual, serta 15 fitur Learning Loop lengkap. Sprint 6: artefak deployment di `deploy/` siap, deploy nyata menunggu akses user ke LXC & Cloudflare.

## 📅 Timeline & Milestone Real

### Sprint Completed
| Sprint | Fokus | Status | Output Real |
|--------|-------|--------|-------------|
| 1 | Ingestion & Smart Chunking | ✅ | PDF, MD, TXT, DOCX, PPTX, HTML, URL, Watch-folder |
| 2 | Query & LLM | ✅ | RAG engine + Hybrid Search (BM25 + ChromaDB) |
| 3 | Semantic Cache | ✅ | Cache aware filter dokumen & relevance floor (`RAG_MIN_SIMILARITY`) |
| 4 | FastAPI & Sessions | ✅ | Session CRUD, SQLite persistent, auto-summary |
| 5 | Custom SPA Frontend | ✅ | React 19 + Vite + Bun (Chat, Library, Quiz, Flashcards, Progress, Settings) |
| 7 | Learning Loop & UI Polish | ✅ | 15 fitur pembelajaran, 100% Custom React Modals, loading indicators |

### Sprint 6 (Deployment LXC + Cloudflare) 🔶
- Systemd unit `rag-backend.service`, `install_lxc.sh`, & `README-DEPLOY.md` di `deploy/` siap.
- Menunggu konfig tunnel `cloudflared` di dashboard.

### Perbaikan dari Audit 2026-08-09 (in progress) 🔶
> Berdasar [`.docs/PROJECT_AUDIT_2026-08-09.md`](../.docs/PROJECT_AUDIT_2026-08-09.md). Detail implementasi belum tentu ada di kode — jangan berasumsi sudah selesai.

- **Auth token aplikasi** (P0-02) — status: in progress (2026-08-09).
- **SSRF protection pada ingest URL** (P0-01) — status: in progress (2026-08-09).
- **Ingestion async + atomic** (P1-01) — status: in progress (2026-08-09).
- **Backup/restore & recovery** (P2-08) — status: in progress (2026-08-09).
- **Quiz attempt server-side + scoring deterministik** (P2-04) — status: in progress (2026-08-09).