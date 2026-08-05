# Architecture & Workflow

## 🏗️ Arsitektur Sistem
┌─────────────────────────────────────────────────────────────┐
│ USER (Browser) │
│ (Akses via Cloudflare) │
└──────────────────────────┬──────────────────────────────────┘
│ HTTPS
▼
┌─────────────────────────────────────────────────────────────┐
│ Cloudflare Tunnel + Access │
│ (Autentikasi & SSL Termination) │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ LXC (Ubuntu/Debian) │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ Streamlit (Port 8501) │ │
│ │ [Frontend UI] │ │
│ └───────────────────────┬───────────────────────────────┘ │
│ │ │
│ ┌───────────────────────▼───────────────────────────────┐ │
│ │ FastAPI (Port 8000) │ │
│ │ [Backend Logic] │ │
│ │ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ │ │
│ │ │ PDF Parser │ │ Embedding │ │ LLM Client │ │ │
│ │ │ & Chunker │ │ Model (Local)│ │ + Cache │ │ │
│ │ └──────────────┘ └──────────────┘ └─────────────┘ │ │
│ └───────────────────────┬───────────────────────────────┘ │
│ │ │
│ ┌───────────────────────▼───────────────────────────────┐ │
│ │ ChromaDB (Persistent Storage) │ │
│ │ [Vector Database + Metadata] │ │
│ └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
│
│ HTTPS (API Call)
▼
┌────────────────────────┐
│ External LLM API │
│ (Limit Besar) │
└────────────────────────┘
## 🔄 Workflow 1: Ingestion (Upload & Indexing Dokumen)
1. User upload PDF via Streamlit UI
│
▼
2. FastAPI terima file, simpan ke folder ./uploads
│
▼
3. PyMuPDF baca PDF, extract text + metadata (page number)
│
▼
4. Smart Chunking:
- Deteksi heading/bab
- Potong per section (max 500 token)
- Overlap 10% antar chunk
│
▼
5. Embedding Model (MiniLM) convert text → vector (768 dim)
│
▼
6. ChromaDB simpan:
- ID unik
- Vector embedding
- Metadata: {source, page, chunk_index}
│
▼
7. UI tampilkan notifikasi: "Dokumen berhasil diindeks"
## 🔄 Workflow 2: Query (Tanya Jawab)
1. User ketik pertanyaan di Streamlit
│
▼
2. GPTCache cek: "Ada pertanyaan mirip di cache?"
│
├─ YES → Return cached answer (0 token!)
│
└─ NO → Lanjut ke step 3
│
▼
3. Embedding Model convert pertanyaan → vector
│
▼
4. ChromaDB similarity search:
- Cari 3 chunk paling mirip (Top-K = 3)
- Return text + metadata
│
▼
5. FastAPI susun prompt:
- System Prompt (ketat & singkat)
- Context (3 chunk tadi)
- User Question
│
▼
6. Kirim ke External LLM API
│
▼
7. Terima response, simpan ke GPTCache
│
▼
8. Tampilkan di UI + source citation

## 💾 Struktur Data ChromaDB

```json
{
  "ids": ["doc1_chunk_0", "doc1_chunk_1", ...],
  "embeddings": [[0.123, -0.456, ...], ...],  // 768 dimensi
  "documents": ["Teks dari chunk 1...", "Teks dari chunk 2..."],
  "metadatas": [
    {
      "source": "Materi_Jaringan.pdf",
      "page": 3,
      "chunk_index": 0,
      "heading": "1.1 Pengertian VLAN"
    },
    ...
  ]
}
```

---

