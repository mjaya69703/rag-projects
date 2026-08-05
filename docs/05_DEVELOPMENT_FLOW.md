# Development Flow

## 📋 Prinsip Pengembangan
1. **Modular:** Setiap fitur dibuat dalam modul terpisah.
2. **Testable:** Setiap modul bisa di-test secara independen.
3. **Iterative:** Develop → Test → Fix → Next Module.

## 🔄 Fase Pengembangan (Sprint)

### Sprint 1: Foundation & PDF Ingestion
**Goal:** Bisa upload PDF dan simpan ke ChromaDB. *(status: 02-08-2026 ✔)*

**Task:**
- [x] Setup folder structure & virtual environment — folder `app/`, `tests/`, `uploads/`, `data/` + venv `.venv` (Python 3.14)
- [x] Install dependencies — `requirements.txt` versi terbaru (chromadb 1.5.9, langchain 1.3.14, dll.)
- [x] Buat script `pdf_parser.py`:
  - [x] Baca PDF dengan PyMuPDF — `extract_pages()` + deteksi heading via font size
  - [x] Extract text per halaman — metadata `page` (1-based)
  - [x] Smart chunking dengan LangChain — `RecursiveCharacterTextSplitter` (chunk 500, overlap 50)
- [x] Buat script `vector_store.py`:
  - [x] Init ChromaDB — persistent di `data/chroma_db`, metrik cosine
  - [x] Load embedding model (MiniLM) — `paraphrase-multilingual-MiniLM-L12-v2` (lazy singleton)
  - [x] Fungsi `add_documents()` dan `search()` — plus `list_documents()`, `delete_document()`, `count()`, `close()`
- [x] Test: Upload 1 PDF, pastikan chunk terbentuk benar — `tests/test_pipeline.py` (pytest 2 passed) + CLI `ingest.py` / `query.py`

**Acceptance Criteria:**
- [x] PDF berhasil di-parse tanpa error
- [x] Chunk terbentuk berdasarkan heading/struktur — 20 chunk, heading bab & sub-bab terdeteksi
- [x] Vektor tersimpan di ChromaDB — `list_documents()` → 20 chunk terindeks
- [x] Metadata (source, page) tersimpan dengan benar — `{source, page, heading, chunk_index}`

---

### Sprint 2: Query & LLM Integration
**Goal:** Bisa tanya jawab dengan dokumen yang sudah diindeks. *(status: 02-08-2026 ✔)*

**Task:**
- [x] Buat script `llm_client.py`:
  - [x] Fungsi untuk call External LLM API — OpenAI-compatible via httpx, konfigurasi dari `.env` (`LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`)
  - [x] System prompt optimization — di `rag_engine.py`: ketat, bahasa sesuai pertanyaan, larang halusinasi, sebut sumber
  - [x] Handle response — `LLMResponse` (text, model, usage) + `LLMError` untuk auth/timeout/format error
- [x] Buat script `rag_engine.py`:
  - [x] Fungsi `query()`:
    - [x] Embed pertanyaan — via `VectorStore.search()`
    - [x] Search di ChromaDB (Top-K = 3)
    - [x] Susun prompt — konteks ber-nomor `[1]..[k]` + pertanyaan
    - [x] Call LLM — `max_tokens=512` (jawaban singkat, latency <5s)
    - [x] Return answer + sources — `RAGAnswer(answer, sources, model)`
- [x] Test: Tanya tentang dokumen yang sudah diupload — `tests/test_rag.py` (pytest 4 passed, pakai LLM mock) + test live via `ask.py`

**Acceptance Criteria:**
- [x] Jawaban relevan dengan konteks dokumen — live test: "Singkatnya VLAN itu apa?" → jawaban sesuai isi dokumen
- [x] Source citation muncul (file & halaman) — `(file: materi_jaringan.pdf, halaman 1)` + list sumber (source, page, heading)
- [x] Respon time < 5 detik — 3.7 detik (model hangat, max_tokens=512; cache Sprint 3 akan mempercepat pertanyaan berulang)

---

### Sprint 3: Semantic Cache
**Goal:** Hemat token dengan cache pertanyaan mirip. *(status: 02-08-2026 ✔)*

**Task:**
- [x] Setup cache persistent — `app/semantic_cache.py` (collection `query_cache` di ChromaDB, threshold cosine 0.25, eviction LRU max 1000)
  - ⚠️ GPTCache 0.1.44 (di spec) **tidak dipakai**: auto-install faiss gagal palsu & memakai API ChromaDB yang sudah deprecated di chromadb 1.5.9 → diganti implementasi sendiri di atas ChromaDB (goal sama: hemat token)
  - 🔁 **e5-small sempat diuji & di-revert** (02-08-2026): lebih baik utk cache (hit rate 73→100%) tapi **retrieval-nya gagal di query bahasa informal** ("ditawarin sama mereka" → nyasar ke chunk lain). Benchmark awal hanya menguji query-vs-query, tidak query-vs-dokumen — kesalahan metodologi. Model tetap **MiniLM-L12**. Keuntungan yang dipertahankan: filter footer template + nomor halaman di parser (chunk 177→147, noise "Intro" 15→1).
- [x] Integrate ke `rag_engine.py`:
  - [x] Cek cache sebelum call LLM — `cache.get(question, where)` → HIT langsung return
  - [x] Simpan ke cache setelah call LLM — `cache.put(...)` dengan answer + model
- [x] Test: Tanya pertanyaan yang sama 2x, pastikan yang ke-2 dari cache — `tests/test_cache.py` (pytest 10 passed total) + demo live

**Acceptance Criteria:**
- [x] Pertanyaan identik/mirip langsung return dari cache — identik (dist 0.0) & parafrase "jelaskan apa itu VLAN" (dist 0.03) HIT; pertanyaan beda makna tetap MISS (anti-false-positive)
- [x] Tidak ada call ke LLM API untuk cached question — diverifikasi dengan mock LLM counter (`calls` tidak bertambah)
- [x] Cache persistent (tidak hilang setelah restart) — tersimpan di ChromaDB persistent, test tutup-buka client lulus

---

### Sprint 4: FastAPI Backend
**Goal:** Expose logic sebagai REST API. *(status: 02-08-2026 ✔)*

**Task:**
- [x] Buat `main.py` dengan FastAPI — `app/main.py`, model & RAG engine di-load sekali via lifespan, ditutup saat shutdown
- [x] Endpoint:
  - [x] `POST /upload`: Upload PDF — validasi .pdf & max 50MB, simpan ke `uploads/`, index (upload ulang = replace), return summary
  - [x] `POST /query`: Tanya jawab — body `{question, top_k?, source?}`, return answer + sources + cached flag
  - [x] `GET /documents`: List dokumen yang sudah diindex
  - [x] `DELETE /documents/{id}`: Hapus dokumen (404 jika tidak ada)
  - [x] Bonus: `GET /health`
- [x] Test — `tests/test_api.py` (6 test: health, full flow upload→query→cache→delete, reject non-PDF, 422 empty question, query tanpa dokumen, delete 404) + **live test via HTTP**: `/health`, `/documents`, `/query` (jawaban LLM nyata + sources) sukses

**Acceptance Criteria:**
- [x] Semua endpoint berjalan tanpa error — pytest 16 passed (10 lama + 6 API)
- [x] Response format konsisten (JSON) — semua endpoint return `{"status": "ok", ...}`; error pakai HTTPException (400/404/422/502)
- [x] Error handling proper — non-PDF→400, PDF scan→400, dokumen tak ada→404, question kosong→422, LLM error→502

**Bonus — Multi-Session Chat (02-08-2026):**
- [x] SQLite (`app/db.py`): tables `sessions`, `messages` (sources JSON), `session_summaries`; FK cascade aktif (`PRAGMA foreign_keys=ON`)
- [x] Session API: `POST /sessions/create`, `GET /sessions/list`, `GET /sessions/{id}/messages`, `PUT /sessions/{id}/rename`, `DELETE /sessions/{id}`
- [x] `POST /query` menerima `session_id` + `mode` (sliding/summary) + `history_n`:
  - Mode sliding: ambil last N pesan (default 15)
  - Mode summary: ringkasan tersimpan + last 5 pesan
  - History non-empty → cache dinonaktifkan (jawaban bergantung konteks)
- [x] Auto-title: pertanyaan pertama → LLM generate judul ≤5 kata
- [x] Auto-summary: setiap 10 pesan → ringkas & simpan ke `session_summaries`
- [x] Token tracking: estimasi token/session + warning >4000
- [x] Test — `tests/test_db.py` (4) + test session di `test_api.py` (4) → **pytest 26 passed**

---

### Sprint 5: Custom Frontend (SPA statis, FastAPI-served)
**Goal:** UI yang user-friendly. *(status: 03-08-2026 ✔ — menggantikan Streamlit; lihat catatan di bawah)*

**Task:**
- [x] Bangun SPA statis tanpa runtime terpisah — `app/static/` (index.html, tokens.css, styles.css, app.js), disajikan langsung oleh FastAPI (mount StaticFiles di `app/main.py`, diprioritaskan setelah route API)
- [x] Layout Workbench: sidebar (session & dokumen), chat region, floating composer — responsive (mobile sidebar slide-in)
- [x] Chat interface: render markdown (marked.js) + code highlighting (highlight.js) + tombol copy, sumber dalam accordion collapsible
- [x] SSE streaming client — `POST /query/stream` via fetch stream reader, event meta/delta/done/error
- [x] Multi-session UI: daftar session (grouping Hari Ini/Kemarin/7 Hari/Sebelumnya), rename, delete, auto-create session pertama setelah `/health`
- [x] Dokumen manager: list + delete + filter source + upload dialog (drag & drop, nama sumber opsional)
- [x] Command palette (`Ctrl/Cmd+K`): chat baru, upload, toggle theme; dark/light theme (localStorage)
- [x] Test — `tests/test_frontend.py` (smoke: shell tersaji, assets OK) + live: `uvicorn app.main:app` → `http://127.0.0.1:8000`

**Catatan (03-08-2026):** Frontend Streamlit (`ui.py`) diganti SPA custom karena: satu proses saja,
tampilan lebih premium, SSE streaming. `test_ui.py` (AppTest) diganti `test_frontend.py`.

**Acceptance Criteria:**
- [x] UI responsive (mobile-friendly) — grid 1 kolom + sidebar slide-in di bawah 960px
- [x] Upload PDF berhasil & ada notifikasi — dialog + toast, feedback error di form
- [x] Chat berjalan smooth dengan streaming — indikator "Menjawab…", cache note, sumber render
- [x] Bisa hapus dokumen & session — konfirmasi + update UI

**Bonus — Hardening Frontend (06-08-2026):**
- [x] XSS fix: sanitasi markdown via DOMPurify sebelum innerHTML
- [x] Tombol stop-streaming (AbortController) + error-state koneksi vs LLM (dengan retry)
- [x] Audit desain Hallmark + anti-slop pass (icon system SVG, token discipline, hapus side-stripe/glow)

---

### Sprint 6: Deployment & Security
**Goal:** Bisa diakses dari mana saja dengan aman.

**Task:**
- [x] Buat artefak deployment — `deploy/` (systemd unit `rag-backend.service`, script `install_lxc.sh`, panduan `README-DEPLOY.md`) — 06-08-2026
- [ ] Install & configure `cloudflared` di LXC (token tunnel dari Zero Trust dashboard)
- [ ] Buat tunnel di Cloudflare Dashboard + public hostname (misal `rag.domain.my.id`)
- [ ] Setup Cloudflare Access policy (email allowlist)
- [ ] Jalankan `install_lxc.sh` di LXC, isi `/opt/rag/.env`, verifikasi `systemctl status rag-backend`
- [ ] Test akses dari external network

**Acceptance Criteria:**
- Bisa diakses via subdomain (misal `rag.domain.my.id`)
- Hanya email yang di-allow yang bisa akses
- Service auto-start setelah reboot