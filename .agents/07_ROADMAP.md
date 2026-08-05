# 07 — Roadmap & Sisa Pekerjaan

## Sprint 6: Deployment & Security (sebagian selesai — artefak siap 06-08-2026) 🔶
Goal: bisa diakses dari mana saja dengan aman via Cloudflare Tunnel.

Selesai 06-08-2026 (artefak di `deploy/`):
- [x] `rag-backend.service` — systemd unit (uvicorn, EnvironmentFile, Restart=always, MemoryMax, harden)
- [x] `install_lxc.sh` — script setup idempotent (user, venv, pip, .env, systemd enable)
- [x] `README-DEPLOY.md` — panduan Cloudflare Tunnel + Access (email allowlist) dalam Bahasa Indonesia

Task tersisa (perlu akses user ke LXC & Cloudflare Dashboard):
- [ ] Install & configure `cloudflared` di LXC (token tunnel dari dashboard)
- [ ] Buat tunnel di Cloudflare Dashboard + public hostname
- [ ] Setup Cloudflare Access policy (email allowlist)
- [ ] Jalankan `install_lxc.sh`, isi `/opt/rag/.env`, verifikasi service
- [ ] Test akses dari external network

Acceptance:
- Akses via subdomain (misal `rag.domain.my.id`)
- Hanya email yang di-allow yang bisa akses
- Service auto-start setelah reboot

### Catatan deployment (penting)
- Target: LXC Ubuntu/Debian, RAM 2-3GB. Torch CPU-only.
- **Monitor RAM saat idle** — target <500MB idle, <1GB saat query. MiniLM ~810MB
  total RSS (delta model ~305MB). e5 lebih besar (jangan dipakai).
- Backend bind `127.0.0.1` saja; akses publik hanya lewat Cloudflare Tunnel.
- `PERSIST_DIR`, `UPLOAD_DIR`, `DB_PATH`, `LLM_*` (+ opsional `RAG_MAX_TOKENS`,
  `CORS_ORIGINS`, `RATE_LIMIT_QPM`, `LOG_DIR`) dari env di LXC.
- Tanpa GPU, tanpa OCR. ChromaDB + MiniLM + SQLite semua embedded (tidak butuh
  server tambahan).

## Backlog / ide (belum diputuskan)
- ~~API rate limiting di backend~~ → **selesai 06-08-2026** (`RATE_LIMIT_QPM`)
- ~~Observability~~ → **selesai 06-08-2026** (cache hit/miss counter + `GET /metrics` + log file)
- Auto top-k (threshold similarity) untuk pertanyaan luas tanpa `-k` manual.
- Deteksi slide-mode di parser (chunk per halaman untuk presentasi).
- Model embedding alternatif (perlu benchmark retrieval dulu, lihat 06#2).
- Multi-user auth (di luar scope v1 — cukup Cloudflare Access single-user).
- Export/import session chat.

## Cara kerja yang disepakati
- Modular, testable, iterative (develop → test → fix).
- Checklist sprint di `docs/05_DEVELOPMENT_FLOW.md` — update tanda `[x]` setiap
  selesai + tulis status & tanggal.
- Simpan pelajaran baru ke `06_LESSONS_LEARNED.md` & project memory.
- Tanya user dulu untuk keputusan besar (ganti model, arsitektur, scope).
