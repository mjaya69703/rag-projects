# 🧠 Personal AI Knowledge Base (Cortex Engine)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/Bun-1.2%2B-fbf0df?style=for-the-badge&logo=bun&logoColor=black" alt="Bun" />
  <img src="https://img.shields.io/badge/ChromaDB-VectorStore-orange?style=for-the-badge" alt="ChromaDB" />
  <img src="https://img.shields.io/badge/Tests-156%20Passing-brightgreen?style=for-the-badge" alt="Tests 100% Pass" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Ready" />
  <img src="https://img.shields.io/badge/License-MIT-purple?style=for-the-badge" alt="MIT License" />
</p>

<p align="center">
  <b>Personal AI Knowledge Base</b> adalah sistem RAG (Retrieval-Augmented Generation) <i>production-grade</i> yang dirancang dengan <b>Laravel-inspired Clean Architecture</b>. Menggabungkan pencarian hybrid (BM25 + Vektor), ingestion multi-format dokumen, dan ekosistem <i>Active Learning Loop</i> (Spaced Repetition SM-2, Kuis AI, Diagnosa Titik Lemah, Mindmap & Glosarium).
</p>

---

## ✨ Fitur Unggulan

### 🔍 1. Hybrid Search & RAG Engine
- **Reciprocal Rank Fusion (RRF)**: Menggabungkan pencarian leksikal kata kunci (BM25) dengan pencarian semantik (ChromaDB + all-MiniLM-L6-v2) untuk akurasi jawaban terbaik.
- **Multi-LLM Native Support**: Mendukung **Groq**, **OpenAI**, **Anthropic (Claude 3.5 Sonnet / Haiku / Opus)**, **OpenRouter**, dan **Ollama (100% Offline)**.
- **Semantic Caching**: Respons instan untuk pertanyaan serupa tanpa membuang kuota LLM token.
- **Citation Grounding**: Kutipan transparan dan akurat langsung ke nomor halaman & heading dokumen sumber.
- **Multi-Session Chat**: Riwayat percakapan persisten dengan SSE (*Server-Sent Events*) real-time streaming.

### 📄 2. Ingestion Dokumen Multi-Format
- Dukungan bawaan: **PDF**, **Markdown**, **TXT**, **DOCX**, **PPTX**, **HTML**, dan **URL Web Scraping**.
- **Anti-SSRF Safe Web Crawler**: Proteksi ketat terhadap IP lokal/privat dan recursive redirects.
- **Automated Watch-Folder**: Cukup drop file ke folder `uploads/`, sistem otomatis mengindeksnya di latar belakang.
- **Checksum Deduplication**: Menghindari indeks duplikat dan mendukung penggantian dokumen secara atomik.

### 🎓 3. Active Learning Ecosystem
- **🎴 3D Spaced Repetition Flashcards**: Antarmuka 3D kartu flip interaktif dengan algoritma penjadwalan memori **SM-2** (*SuperMemo-2*).
- **🎯 AI Quiz Arena**: Pembuat kuis pilihan ganda otomatis dengan sistem penilaian deterministik di server dan ringkasan akurasi.
- **📚 Knowledge Glossary**: Kamus istilah penting dengan fitur 1-klik ekstraksi konsep kunci via AI.
- **📊 Weak-Spots Diagnostics**: Analisis mendalam topik-topik yang sering salah atau lupa beserta radar penguasaan materi (*Mastery Radar*).

### 🛡️ 4. Privasi & Database Migrations
- **Laravel-style Migrations & Seeders**: Migrasi database terstruktur (`cortex migrate`, `cortex migrate:fresh`, `cortex db:seed`).
- **Local-First Storage**: Dokumen dan riwayat chat tersimpan lokal di mesin Anda (SQLite + ChromaDB).
- **PII Auto-Redaction**: Sensor otomatis email, nomor telepon, dan pola kredensial sebelum dikirim ke penyedia LLM.
- **1-Click Data Purge**: Kemampuan membersihkan seluruh riwayat chat, kuis, dan semantic cache kapan saja.

### 🔌 5. Integrasi Eksternal
- **Model Context Protocol (MCP)**: Server FastMCP bawaan untuk dihubungkan langsung dengan Cursor, Claude Desktop, atau Antigravity.
- **Telegram Bot**: Asisten pengetahuan pribadi yang siap menjawab pertanyaan lewat pesan Telegram.

---

## ⚡ 1-Minute Quick Start

### Opsi A: Sekali Klik (Windows / Linux / macOS)

**Windows:**
```powershell
start.cmd
```

**Linux / macOS / WSL:**
```bash
chmod +x start.sh
./start.sh
```
> Script di atas otomatis menyiapkan virtual environment `.venv`, menginstal dependensi yang dibutuhkan, dan langsung menyalakan server di **http://127.0.0.1:8000**.

---

### Opsi B: Manual via Cortex CLI

1. **Clone repository & siapkan environment:**
   ```bash
   git clone https://github.com/mjaya69703/rag-projects.git
   cd rag-projects
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Inisialisasi konfigurasi & database:**
   ```bash
   python cortex setup
   ```

3. **Konfigurasikan API Key LLM:**
   Edit file `.env` dan masukkan API Key LLM Anda (OpenAI, Groq, Anthropic, OpenRouter, atau Ollama):
   ```ini
   # Contoh Groq
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_your_groq_api_key_here

   # Contoh Anthropic (Claude 3.5 Sonnet)
   # LLM_PROVIDER=anthropic
   # ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
   ```

4. **Nyalakan aplikasi:**
   ```bash
   python cortex serve
   ```
   Buka browser di **http://127.0.0.1:8000**.

---

### Opsi C: Docker & Docker Compose

Jalankan seluruh stack RAG dan frontend dengan satu perintah:

```bash
docker compose up -d --build
```
Aplikasi langsung berjalan di `http://localhost:8000`.

---

## 💻 Cortex CLI Reference

Semua operasi backend, ingestion, migrasi database, dan pengujian dikendalikan melalui satu command runner: **`cortex`** (otomatis memakai `.venv`).

| Command | Argumen | Deskripsi |
| :--- | :--- | :--- |
| `cortex serve` | `[--port 8000] [--host 0.0.0.0]` | Menjalankan FastAPI server & UI |
| `cortex ingest` | `<file \| folder \| url> [-c Kategori]` | Mengindeks dokumen / folder / tautan web |
| `cortex query` | `[pertanyaan]` | Mode tanya jawab interaktif / langsung di terminal |
| `cortex migrate` | `[--seed]` | Menjalankan database migrations |
| `cortex migrate:fresh` | `[--seed]` | Drop semua tabel & jalankan migrasi dari awal |
| `cortex migrate:reset` | — | Rollback seluruh tabel database |
| `cortex db:seed` | — | Mengisi data glossary & sample flashcards awal |
| `cortex build` | — | Meng-compile frontend React 19 SPA via Bun |
| `cortex test` | `[pytest-args]` | Menjalankan seluruh 156 automated test suite |
| `cortex setup` | — | Inisialisasi awal database, migrasi & folder |

> **Catatan Windows PowerShell**: Gunakan `.\cortex <command>` (misal: `.\cortex serve`). Di Command Prompt (CMD) cukup ketik `cortex <command>`.

### Contoh Penggunaan CLI:
```bash
# Ingest satu buku PDF
cortex ingest uploads/buku_jaringan.pdf --category Jaringan

# Ingest seluruh folder dokumentasi
cortex ingest ./materi_kuliah/ --category Edukasi

# Ingest dari URL web
cortex ingest https://docs.python.org/3/tutorial/

# Fresh migrasi dan seeding database
cortex migrate:fresh --seed

# Tanya jawab lewat terminal
cortex query "Bagaimana cara kerja OSPF routing?"
```

---

## 🏛️ Arsitektur Proyek (Clean Architecture)

```
rag-projects/
├── app/
│   ├── Http/
│   │   ├── Controllers/             # 🎮 Route Handlers (Chat, Document, Learning, Glossary, Analytics)
│   │   ├── Requests/                # 📝 Pydantic DTOs & Validation Schemas
│   │   └── Routes.py                # 🚦 Central API Router
│   ├── Models/                      # 📦 Domain Entities & Schemas (Session, Message, Quiz, Document)
│   ├── Repositories/                # 🗄️ Data Access (SQLite, ChromaDB, Semantic Cache)
│   ├── Services/                    # 🧠 Pure Business Logic (RAG Engine, SM-2, Ingestion Pipeline)
│   │   └── Parsers/                 # 📄 Multi-format Parsers (PDF, MD, DOCX, PPTX, HTML, URL)
│   ├── Console/                     # 💻 Command Implementations (Serve, Ingest, Query, Migrate, Seed)
│   ├── Integrations/                # 🔌 MCP Server & Telegram Bot
│   ├── Core/                        # ⚙️ App Settings & Database Factory
│   └── main.py                      # 🎯 FastAPI Entrypoint
├── database/
│   ├── migrations/                  # 🗃️ Database Migrations (001_create_sessions, 002_create_docs, etc.)
│   └── seeders/                     # 🌱 Database Seeders (GlossarySeeder, SampleCardSeeder)
├── frontend/                        # 🎨 Views (React 19 + TypeScript SPA)
│   └── src/
│       ├── pages/                   # Chat, Library, Flashcards, Quiz, Glossary, Progress, Settings
│       └── shared/                  # 📦 Shared Component Library & Services
│           ├── components/          # Button, Card, Modal, Input, Badge, Tabs, StatCard, SourceCard
│           ├── services/            # Strongly-typed API client per domain
│           └── hooks/               # useTheme, useToast
├── tests/                           # 🧪 Pytest Suite (156 tests 100% PASS)
├── cortex.py                        # ⚡ Unified Cortex Command Runner
├── start.cmd / start.sh             # 🚀 1-Click Application Launchers
├── Dockerfile & docker-compose.yml  # 🐳 Multi-Stage Docker Containerization
└── requirements.txt                 # 🐍 Python Dependencies
```

---

## ⚙️ Konfigurasi Environment (`.env`)

| Variabel | Default | Deskripsi |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `groq` | Penyedia LLM: `groq`, `openai`, `anthropic`, `openrouter`, `ollama` |
| `GROQ_API_KEY` | — | API key untuk Groq |
| `OPENAI_API_KEY` | — | API key untuk OpenAI |
| `ANTHROPIC_API_KEY` | — | API key untuk Anthropic Claude |
| `OPENROUTER_API_KEY` | — | API key untuk OpenRouter |
| `LLM_MODEL` | Provider default | Nama model LLM yang digunakan |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | Lokasi penyimpanan vector store |
| `DB_PATH` | `./data/chat.db` | Lokasi database SQLite |
| `REDACTION_ENABLED` | `true` | Sensor otomatis PII (email/telepon) sebelum ke LLM |
| `RETAIN_CHAT_DAYS` | `30` | Hapus chat yang tidak diakses lebih dari N hari (0 = selamanya) |
| `AUTH_API_TOKEN` | — | Kunci otentikasi Bearer opsional |

---

## 🧪 Testing & Quality Assurance

Proyek ini dilengkapi dengan cakupan unit & integration test yang komprehensif:

```bash
# Menjalankan seluruh test suite
python cortex test
```
*Hasil:* **156 passed** (100% PASS).

---

## 🤝 Berkontribusi

Kontribusi selalu terbuka! Silakan:
1. Fork repository ini.
2. Buat feature branch (`git checkout -b feature/FiturKeren`).
3. Commit perubahan (`git commit -m 'feat: Tambah fitur keren'`).
4. Push ke branch (`git push origin feature/FiturKeren`).
5. Buat Pull Request.

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi **MIT**. Lihat file `LICENSE` untuk informasi lebih lanjut.
