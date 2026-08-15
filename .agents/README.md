# .agents — Handover Pack Proyek RAG

Folder ini adalah **handover pack** untuk agent AI (Qwen Code / Claude / dll.) yang
akan meneruskan pekerjaan proyek ini, kemungkinan di PC lain. Baca file berikut
berurutan supaya konteks lengkap:

| Urutan | File | Isi |
|--------|------|-----|
| 1 | `00_PROJECT_OVERVIEW.md` | Apa proyek ini, status, fitur, milestone |
| 2 | `01_TECH_STACK.md` | Stack & keputusan teknis (Python 3.13, React 19 + Bun) |
| 3 | `02_ARCHITECTURE.md` | Struktur folder, modul, alur kerja RAG & frontend |
| 4 | `03_WINDOWS_QUIRKS.md` | Bug & workaround Windows yang wajib diketahui |
| 5 | `04_SESSION_CHAT.md` | Desain multi-session chat persistent |
| 6 | `05_TESTING.md` | Cara test & run, perintah CLI, bun build |
| 7 | `06_LESSONS_LEARNED.md` | Pelajaran penting — baca sebelum ubah apa pun |
| 8 | `07_ROADMAP.md` | Sisa pekerjaan (Sprint 6 deployment LXC) + backlog |
| 9 | `08_CUSTOM_FRONTEND_HANDOVER.md` | Panduan arsitektur React 19 SPA, Bun build, custom modals, loading states |

## Cara pakai untuk agent penerus

1. Baca file 00-08 di atas (sekali, berurutan).
2. Verifikasi asumsi di file dengan membaca kode aktual sebelum bertindak.
3. Ikuti konvensi: modular, testable, jangan rombak API tanpa update test.
4. Perubahan frontend wajib di-build via `bun run build` di folder `frontend/`.
5. Jangan commit `.env` (berisi API key LLM).

## Status Terkini (07-08-2026)

- **Sprint 1–5 & 7 Selesai 100%**: Ingestion multi-format, RAG query, hybrid search, semantic cache, FastAPI + session API, MCP Server, Bot Telegram, dan 15 fitur Learning Loop.
- **Frontend SPA**: React 19 + Vite + React Router (Bun). Di-build ke `app/static/` via `bun run build`.
- **UI Design System**: OKLCH Glassmorphism, 100% custom React Modals (`ConfirmDialog`, `PromptDialog`), serta indikator loading & spinner visual di semua aksi async.
- **Sprint 6 (Deployment LXC + Cloudflare)**: Artefak di `deploy/` siap.

## Status Implementasi & Verifikasi (2026-08-09, berdasar audit)

> Sumber: `.docs/PROJECT_AUDIT_2026-08-09.md`. Status "selesai 100%" berarti **implementasi fitur**, BUKAN berarti **terverifikasi produksi**. Daftar di bawah memisahkan keduanya dengan jujur — jangan mengklaim terverifikasi kalau audit belum membuktikannya.

### Implemented & Verified ✅
- Ingestion multi-format (PDF, MD, TXT, DOCX, PPTX, HTML, URL, Watch-folder) — parse & persist.
- Hybrid search (BM25 + ChromaDB), semantic cache custom, relevance floor.
- FastAPI + session chat (SQLite), streaming SSE, frontend SPA tersaji dari `app/static/`.
- Test subset parser/database/ingestion: **47 pass** (diverifikasi ulang saat audit, `--basetemp .pytest-tmp`).

### Implemented tapi Belum Terverifikasi Penuh ⚠️
- **Suite API pytest**: dilaporkan 106 passed (07-08-2026) di `.agents/05_TESTING.md`, tapi **belum dapat dipastikan pass** di environment audit (gagal saat model embedding mencoba akses Hugging Face). Perlu dijalankan ulang di environment dengan model tersedia.
- **Frontend build** (`bun run build`): gagal di environment audit karena EPERM pada `frontend/node_modules/picomatch/index.js` — perlu dibersihkan/di-install ulang lalu di-build lagi.
- **Latency/RAM benchmark**: target <5 detik & <1.5 GB belum terbukti dengan pengukuran formal.
- **LLM tests**: hanya sebagian (unit dengan mock); test nyata ke API LLM belum lengkap.
- **Browser E2E / penilaian visual**: belum dijalankan (audit tidak menjalankan browser).

### Belum Ada / In Progress (2026-08-09) 🔶
> Fitur-fitur berikut direncanakan dari temuan audit dan **belum tentu ada di kode** — cek kode sebelum menganggapnya tersedia.
- Auth token aplikasi (P0-02) — status: in progress.
- SSRF protection pada ingest URL (P0-01) — status: in progress.
- Ingestion async + atomic (P1-01) — status: in progress.
- Backup/restore & recovery (P2-08) — status: in progress.
- Quiz attempt server-side + scoring deterministik (P2-04) — status: in progress.
- Security tests (SSRF/auth), observability (metrics Prometheus-compatible), document registry (P1-02) — belum dimulai.
