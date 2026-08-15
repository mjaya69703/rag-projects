# Goals & Scope

> ⚠️ **DOKUMEN HISTORIS (sebagian)** — Ditulis untuk rencana awal (Streamlit + PDF-only). Bagian yang sudah tidak sesuai telah diperbaiki per 2026-08-09; isi historis lain tetap dipertahankan. **Untuk stack & arsitektur aktual, lihat [`.agents/README.md`](../.agents/README.md) sebagai referensi kanonik.**

## 🎯 Goals (Tujuan)
1. **Membangun Personal Knowledge Base** yang bisa di-query menggunakan bahasa natural.
2. **Belajar Implementasi RAG** dari nol (Embedding, Vector DB, LLM Integration).
3. **Optimasi Resource** agar bisa berjalan di environment terbatas (LXC 2-3GB RAM).
4. **Efisiensi Token API** dengan teknik caching dan prompt engineering.
5. **Mendapatkan Portofolio** yang relevan dengan tren industri AI 2026.

## ✅ In-Scope (Yang Dikerjakan)
- Backend Python (FastAPI) untuk logic RAG.
- Frontend SPA **React 19 + Vite + Bun** (menggantikan rencana awal Streamlit — sudah diimplementasi sejak 03-08-2026).
- Embedding Model lokal (`paraphrase-multilingual-MiniLM-L12-v2`).
- Vector Database lokal (ChromaDB) + Hybrid Search (BM25 + vector).
- Integrasi dengan API LLM eksternal.
- Smart Chunking (berdasarkan struktur dokumen).
- Semantic Cache custom di ChromaDB (bukan GPTCache) untuk hemat token.
- Deployment via Cloudflare Tunnel.

## ❌ Out-of-Scope (TIDAK Dikerjakan di Versi 1)
- Training/Fine-tuning model LLM sendiri.
- ~~Support format file selain PDF~~ — **SUDAH DIIMPLEMENTASI (07-08-2026):** MD, TXT, DOCX, PPTX, HTML, URL, Watch-Folder.
- Multi-user authentication system (cukup single-user dengan CF Access) — *catatan 2026-08-09: auth aplikasi (token) sedang direncanakan, lihat audit `../.docs/PROJECT_AUDIT_2026-08-09.md`.*
- OCR untuk PDF hasil scan (hanya PDF text-based).
- Mobile app native (cukup web responsive).

## 🚫 Batasan & Asumsi
- **Batasan:** RAM LXC maksimal 3GB.
- **Asumsi:** API LLM eksternal memiliki limit yang cukup besar dan latency < 2 detik.
- **Asumsi:** Dokumen yang diupload adalah text-based (bukan scan/gambar); OCR tidak didukung. Format aktual: PDF, MD, TXT, DOCX, PPTX, HTML, URL.