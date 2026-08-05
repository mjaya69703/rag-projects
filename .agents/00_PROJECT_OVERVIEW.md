# 00 — Project Overview

## Apa ini
**Personal AI Knowledge Base (RAG)** — sistem tanya-jawab dari dokumen PDF pribadi
(materi kuliah, presentasi kantor). Embedding lokal, LLM API eksternal, dioptimasi
untuk environment terbatas (LXC 2-3GB RAM). Bahasa: Indonesia + Inggris.

## Status sprint (per 06-08-2026)
| Sprint | Fokus | Status |
|--------|-------|--------|
| 1 | PDF Ingestion (PyMuPDF + chunking + ChromaDB) | ✅ |
| 2 | Query & LLM (RAG engine) | ✅ |
| 3 | Semantic Cache | ✅ |
| 4 | FastAPI Backend (+ session management API) | ✅ |
| 5 | Custom Frontend (SPA statis, FastAPI-served) | ✅ |
| 6 | Deployment & Security (Cloudflare Tunnel) | 🔶 artefak siap di `deploy/` (06-08-2026), deploy nyata menyusul |

06-08-2026: hardening keamanan (semantic cache aware filter dokumen, validasi PDF asli,
CORS eksplisit, rate limit, observability) + audit desain frontend (Hallmark) + pin dependency.

## Fitur utama
- Upload PDF → smart chunking berbasis heading → embedding lokal → ChromaDB
- Tanya-jawab dengan source citation (file, halaman, heading)
- Semantic cache (pertanyaan identik/parafrase → tanpa call LLM)
- Multi-session chat persistent (SQLite): sliding window / summary mode
- Auto-title session, auto-summary tiap 10 pesan, warning token >4000

## Dokumentasi sumber
Spesifikasi & roadmap asli ada di `docs/`:
`01_PRD.md`, `02_GOALS_AND_SCOPE.md`, `03_TECHNICAL_SPECIFICATION.md`,
`04_ARCHITECTURE_AND_WORKFLOW.md`, `05_DEVELOPMENT_FLOW.md`, `06_ROADMAP.md`,
`07_TESTING_AND_QA.md`, `README.md` (arsip v1).

## Environment
- OS dev: **Windows** (cmd.exe). Target deploy: Ubuntu/Debian LXC.
- Python 3.13 di mesin ini (catatan 02-08-2026: handover lama bilang 3.14, tapi PC
  ini cuma ada 3.13 — venv direbuild dengan 3.13, lihat `01_TECH_STACK.md`).
- Semua dependency versi terbaru (lihat `01_TECH_STACK.md`).
