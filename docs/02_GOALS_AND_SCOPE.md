# Goals & Scope

## 🎯 Goals (Tujuan)
1. **Membangun Personal Knowledge Base** yang bisa di-query menggunakan bahasa natural.
2. **Belajar Implementasi RAG** dari nol (Embedding, Vector DB, LLM Integration).
3. **Optimasi Resource** agar bisa berjalan di environment terbatas (LXC 2-3GB RAM).
4. **Efisiensi Token API** dengan teknik caching dan prompt engineering.
5. **Mendapatkan Portofolio** yang relevan dengan tren industri AI 2026.

## ✅ In-Scope (Yang Dikerjakan)
- Backend Python (FastAPI) untuk logic RAG.
- Frontend sederhana (Streamlit) untuk UI.
- Embedding Model lokal (`paraphrase-multilingual-MiniLM-L12-v2`).
- Vector Database lokal (ChromaDB).
- Integrasi dengan API LLM eksternal.
- Smart Chunking (berdasarkan struktur dokumen).
- Semantic Cache untuk hemat token.
- Deployment via Cloudflare Tunnel.

## ❌ Out-of-Scope (TIDAK Dikerjakan di Versi 1)
- Training/Fine-tuning model LLM sendiri.
- Support format file selain PDF (DOCX, PPTX akan ditunda).
- Multi-user authentication system (cukup single-user dengan CF Access).
- OCR untuk PDF hasil scan (hanya PDF text-based).
- Mobile app native (cukup web responsive).

## 🚫 Batasan & Asumsi
- **Batasan:** RAM LXC maksimal 3GB.
- **Asumsi:** API LLM eksternal memiliki limit yang cukup besar dan latency < 2 detik.
- **Asumsi:** Dokumen yang diupload adalah PDF text-based (bukan scan/gambar).