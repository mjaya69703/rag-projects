# Technical Specification

> ⚠️ **DOKUMEN HISTORIS — TIDAK AKTIF** — Spec di bawah ditulis untuk **stack lama** (Streamlit, GPTCache, LangChain 0.1, chromadb 0.4.22) dan **JANGAN diikuti**. Aplikasi aktual memakai **FastAPI + React 19/Vite/Bun SPA + ChromaDB 1.5.x + MiniLM + hybrid search (BM25+vector) + semantic cache custom di ChromaDB**. Versi dependency aktual ada di lampiran bawah halaman ini. **Referensi kanonik: [`.agents/README.md`](../.agents/README.md) (terutama `01_TECH_STACK.md` & `02_ARCHITECTURE.md`).**

## 🖥️ Infrastructure
| Komponen | Spesifikasi |
|----------|-------------|
| Host | VMware Workstation (Windows) |
| Hypervisor | Proxmox VE |
| Total RAM Host | 8 GB |
| LXC OS | Ubuntu 22.04 / Debian 12 |
| LXC Resources | 2 Core CPU, 3 GB RAM, 20 GB Storage |
| Network | Cloudflare Tunnel (cloudflared) |

## 🛠️ Tech Stack
| Layer | Teknologi | Alasan |
|-------|-----------|--------|
| Backend | Python 3.10+ + FastAPI | Cepat, modern, async support |
| Frontend | Streamlit | Cepat develop, UI bagus, pure Python |
| Embedding Model | `paraphrase-multilingual-MiniLM-L12-v2` | Ringan (~130MB), support Indo+English; tolerant query informal. e5-small diuji 02-08-2026 & di-revert (retrieval lemah di bahasa gaul) |
| Vector DB | ChromaDB | Embedded, no server needed, persistent |
| PDF Parser | `PyMuPDF` (fitz) + `unstructured` | Akurat, support layout detection |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | Smart chunking dengan overlap |
| LLM Integration | OpenAI-compatible API / Custom API | Fleksibel, limit besar |
| Caching | `gptcache` + SQLite | Semantic cache, hemat token |
| Reverse Proxy | Cloudflare Tunnel | HTTPS otomatis, no port forwarding |
| Auth | Cloudflare Access (Zero Trust) | Aman, gratis, email-based |

## 📦 Dependency Utama (requirements.txt)
fastapi==0.109.0
uvicorn==0.27.0
streamlit==1.31.0
langchain==0.1.5
langchain-community==0.0.20
chromadb==0.4.22
sentence-transformers==2.3.1
pymupdf==1.23.8
unstructured==0.12.0
gptcache==0.1.43
python-dotenv==1.0.0
httpx==0.26.0

## 🔐 Security
- Semua endpoint di-expose via Cloudflare Tunnel (tidak ada port yang dibuka ke publik).
- Cloudflare Access policy: Hanya email tertentu yang bisa akses.
- API Key LLM disimpan di `.env` file, tidak di-commit ke git.

---

## 📎 Lampiran — Stack & Dependency AKTUAL (diperbarui 2026-08-09)

> Bagian ini menggantikan tabel tech stack & dependency lama di atas. Sumber: `requirements.txt`, `frontend/package.json`, dan `.agents/01_TECH_STACK.md`.

| Layer | Teknologi Aktual |
|-------|------------------|
| Backend | FastAPI + uvicorn (Python 3.13) |
| Frontend | **React 19 + Vite + React Router**, dikelola **Bun**, di-build ke `app/static/` |
| Styling | Vanilla CSS OKLCH tokens + Glassmorphism (`tokens.css`, `styles.css`) |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` (lokal, via sentence-transformers) |
| Vector DB | ChromaDB **1.5.9** (persistent `data/chroma_db`, cosine) |
| Hybrid Search | **BM25** (`rank_bm25`) + vector |
| Parsers | PyMuPDF (PDF), python-docx, python-pptx, bs4/markdown |
| Chunking | LangChain **1.3.14** `RecursiveCharacterTextSplitter` (`langchain-text-splitters` 1.1.2) + smart heading detection |
| LLM | OpenAI-compatible endpoint databyte AI (`deepseek-v4-flash`), via httpx |
| Semantic cache | **Custom di ChromaDB** (collection `query_cache`) — GPTCache dihapus |
| Chat & Learning DB | SQLite (`data/chat.db`) |
| HTTP client | httpx |
| Access layers | MCP Server (`mcp`), Bot Telegram (`python-telegram-bot`) |

**Dependency backend aktual (`requirements.txt`, 2026-08-09):**
```
fastapi==0.141.1
uvicorn==0.52.1
python-multipart==0.0.32
langchain==1.3.14
langchain-community==0.4.2
langchain-text-splitters==1.1.2
chromadb==1.5.9
sentence-transformers==5.6.1
rank_bm25==0.2.2
pymupdf==1.28.0
unstructured==0.25.0
python-docx==1.2.0
python-pptx==1.0.2
python-dotenv==1.2.2
httpx==0.28.1
mcp==1.29.0
python-telegram-bot==22.8
pytest==9.1.1
ruff==0.16.1
psutil==7.2.2
```

**Dependency frontend aktual (`frontend/package.json`):** react/react-dom ^19.2.8, react-router-dom ^7.18.2, vite ^8.2.1, @vitejs/plugin-react ^6.0.5, marked ^18.0.9, dompurify ^3.4.13, highlight.js ^11.11.1.

**Security (status 2026-08-09):** Cloudflare Tunnel + Access tetap menjadi lapisan deployment. Catatan audit P0-02: endpoint aplikasi **belum** memiliki autentikasi/otorisasi sendiri — mitigasi (auth token aplikasi) **in progress**. Lihat `.docs/PROJECT_AUDIT_2026-08-09.md`.