# .agents — Handover Pack Proyek RAG

Folder ini adalah **handover pack** untuk agent AI (Qwen Code / Claude / dll.) yang
akan meneruskan pekerjaan proyek ini, kemungkinan di PC lain. Baca file berikut
berurutan supaya konteks lengkap:

| Urutan | File | Isi |
|--------|------|-----|
| 1 | `00_PROJECT_OVERVIEW.md` | Apa proyek ini, status, fitur, milestone |
| 2 | `01_TECH_STACK.md` | Stack & keputusan teknis (penting: py3.14, dep terbaru) |
| 3 | `02_ARCHITECTURE.md` | Struktur folder, modul, alur kerja |
| 4 | `03_WINDOWS_QUIRKS.md` | Bug & workaround Windows yang wajib diketahui |
| 5 | `04_SESSION_CHAT.md` | Desain multi-session chat (Sprint 4-5 bonus) |
| 6 | `05_TESTING.md` | Cara test & run, perintah CLI |
| 7 | `06_LESSONS_LEARNED.md` | Pelajaran penting — baca sebelum ubah apa pun |
| 8 | `07_ROADMAP.md` | Sisa pekerjaan (Sprint 6) + backlog ide |

## Cara pakai untuk agent penerus

1. Baca file 00-08 di atas (sekali, berurutan).
2. Verifikasi asumsi di file dengan membaca kode aktual sebelum bertindak
   (memory bisa basi — kode adalah kebenaran terkini).
3. Ikuti konvensi: modular, testable, jangan rombak API tanpa update test.
4. `docs/` berisi dokumen spesifikasi asli (PRD, spec, roadmap) — tetap sumber kebenaran untuk requirement.
5. Jangan commit `.env` (berisi API key LLM).

## Status singkat

> Update 06-08-2026: hardening keamanan (cache aware filter dokumen, validasi PDF,
> CORS eksplisit, rate limit, observability) + audit desain frontend (Hallmark) +
> pin dependency + artefak deployment Sprint 6 di `deploy/`.
> Update frontend 03-08-2026: Streamlit telah diganti UI custom yang disajikan langsung dari FastAPI.

Sprint 1-5 **selesai** (ingestion, RAG query, semantic cache, FastAPI + session API,
custom SPA multi-session). Sprint 6 (deployment Cloudflare) artefaknya siap, deploy
nyata menunggu akses user ke LXC & Cloudflare Dashboard.
