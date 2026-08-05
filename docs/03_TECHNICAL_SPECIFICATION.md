# Technical Specification

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