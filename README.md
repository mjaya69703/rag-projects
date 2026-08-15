# Personal AI Knowledge Base (RAG System)

Aplikasi RAG (*Retrieval-Augmented Generation*) berbasis web untuk menyimpan dokumen pribadi (PDF, MD, TXT, DOCX, PPTX, HTML, URL) dan melakukan tanya-jawab presisi dengan AI. Dilengkapi fitur latihan soal (Quiz), flashcards 3D, tracking progress belajar, MCP Server, dan Bot Telegram.

---

## ⚡ Cara Cepat Menjalankan Aplikasi

```cmd
rem 1. Jalankan aplikasi (Backend FastAPI + Frontend React SPA)
start.cmd
```
> Buka browser di **`http://127.0.0.1:8000`**

### Bila ada perubahan pada kode frontend (`frontend/`):
```cmd
cd frontend
bun install
bun run build
```

### Menjalankan via Docker Compose:
```bash
# 1. Siapkan konfigurasi (wajib sekali) — salin lalu isi LLM_API_KEY / LLM_API_BASE / LLM_MODEL
cp .env.example .env

# 2. Build & jalankan
docker compose up -d --build
```
> Buka browser di **`http://localhost:8000`**
> **Catatan:** pada first run, container mengunduh model embedding MiniLM (~90 MB) dari HuggingFace, jadi butuh koneksi internet.

---

## 🧭 6 Halaman Utama Aplikasi

| Halaman | URL | Fungsi Utama |
|---|---|---|
| 💬 **Chat** | `/` | Tanya-jawab streaming dengan AI (SSE), rujukan sumber halaman/heading, filter dokumen, & prompt suggestion chips. |
| 📚 **Library** | `/library` | Manajemen file dokumen terindeks, pratinjau isi chunk, editor catatan (annotations), & antrean review. |
| 🎯 **Quiz** | `/quiz` | Pembuat soal pilihan ganda (A/B/C/D) dari materi dokumen, koreksi otomatis + penjelasan AI, & riwayat skor. |
| 🎴 **Flashcards** | `/flashcards` | Kartu hafalan 3D (*flip card* via klik/`Spasi`), indikator penguasaan materi, & navigasi keyboard. |
| 📊 **Progress** | `/progress` | Dashboard analitik pembelajaran (stat KPI, cakupan bab per dokumen, & matriks area lemah). |
| ⚙️ **Settings** | `/settings` | Switcher tema (Dark Slate / Light), metrik kesehatan sistem, Semantic Cache hit rate, & integrasi MCP/Telegram. |

---

## 🛠️ Fitur & Arsitektur Utama (Real Codebase)

### 1. Ingestion & Retrieval (`app/`)
- **Multi-Format Parser**: PDF (`pdf_parser.py`), Markdown (`md_parser.py`), Office DOCX/PPTX/HTML (`office_parser.py`), URL Scraper (`url_parser.py`).
- **Auto Watch-Folder**: File yang di-drop ke folder `uploads/` otomatis terindeks setiap 30 detik (`watch_folder.py`).
- **Hybrid Search**: Penggabungan pencarian kata kunci BM25 + vektor ChromaDB (`hybrid_search.py`).
- **Relevance Floor / Grounding**: Menolak menjawab jika skor relevansi dokumen di bawah batas (`RAG_MIN_SIMILARITY`).
- **Semantic Cache**: Menyimpan jawaban pertanyaan identik/parafrase untuk menghemat token LLM (`semantic_cache.py`).

### 2. Frontend Modern (`frontend/`)
- **Teknologi**: React 19 + Vite + React Router SPA (dikelola **Bun**).
- **UI Design System**: Vanilla CSS dengan OKLCH Glassmorphism, responsif, & support Dark/Light mode.
- **100% Custom Modals**: Tanpa popup bawaan browser `confirm/prompt` (menggunakan `<ConfirmDialog>` & `<PromptDialog>`).
- **Visual Loading Indicators**: Tombol async dilengkapi spinner `.spinner`, serta animasi titik berdenyut `.typing-dots` saat AI berpikir.

### 3. Akses Eksternal Layer
- **MCP Server** (`.venv\Scripts\python -m app.mcp_server`): Hubungkan Knowledge Base ke Claude Desktop / Cursor AI.
- **Bot Telegram** (`.venv\Scripts\python -m app.telegram_bot`): Tanya-jawab & upload dokumen langsung dari Telegram HP.

---

## 🧪 Testing & Verifikasi

```cmd
rem 1. Test build frontend (Vite + Bun)
cd frontend && bun run build

rem 2. Test backend unit test suite (pytest - 106 tests passed)
.venv\Scripts\python -m pytest tests\ -q
```

---

## 📁 Struktur Folder Utama

```
rag-projects/
├── frontend/          # React 19 SPA (pages, components, styles)
├── app/               # FastAPI backend (parsers, RAG engine, DB, MCP, Telegram)
├── app/static/        # Hasil build frontend (bun run build)
├── uploads/           # Folder tempat menyimpan & watch-folder dokumen
├── data/              # Storage ChromaDB & SQLite chat.db
├── deploy/            # Artefak deployment LXC systemd
├── tests/             # 106 unit & integration test files
└── start.cmd          # Script 1-klik untuk running aplikasi
```
