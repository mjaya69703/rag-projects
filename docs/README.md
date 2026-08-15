# Personal AI Knowledge Base (RAG System)

## 📌 Deskripsi Singkat
Sistem *Retrieval-Augmented Generation* (RAG) pribadi yang memungkinkan pengguna mengunggah dokumen (PDF, MD, TXT, DOCX, PPTX, HTML, URL), lalu melakukan tanya-jawab dengan AI berdasarkan konteks dari dokumen tersebut. Sistem ini dioptimasi untuk berjalan di *resource-constrained environment* (LXC dengan RAM 2-3GB) dan menggunakan API LLM eksternal untuk efisiensi.

> **Status dokumentasi (diperbarui 2026-08-09):** Sebagian dokumen di folder `docs/` ditulis untuk stack lama (Streamlit/GPTCache/LangChain 0.1) dan sekarang **historis**. Referensi kanonik yang akurat ada di [`.agents/`](../.agents/README.md). Lihat tabel pemetaan di bawah.

## 🎯 Tujuan Utama
Menyediakan "Otak Kedua" (*Second Brain*) yang dapat diakses dari mana saja, mampu memahami dokumen berbahasa Indonesia dan Inggris, serta hemat penggunaan token API.

## 🚀 Fitur Utama (Aktual, per 07-08-2026)
1. **Upload Multi-Format:** PDF, MD, TXT, DOCX, PPTX, HTML, URL, & Watch-Folder `uploads/` — dengan *smart chunking* (berbasis heading/struktur + `RecursiveCharacterTextSplitter`).
2. **Chat Interface:** SPA **React 19 + Vite + Bun** (disajikan FastAPI dari `app/static/`) dengan SSE streaming.
3. **Source Tracking:** AI menyebutkan dari halaman/file/heading mana jawaban diambil.
4. **Hybrid Search:** BM25 + ChromaDB vector similarity (bukan sekadar vector search).
5. **Semantic Cache Custom:** Implementasi sendiri di ChromaDB (collection `query_cache`) — *bukan* GPTCache.
6. **Akses Remote:** Deployment via Cloudflare Tunnel dengan autentikasi Zero Trust (artefak di `deploy/`).
7. **Learning Loop:** 15 fitur (Quiz, Flashcards 3D, Progress Analytics, Spaced Repetition, Weak-spots).

## 📚 Dokumentasi — Pemetaan Kanonik vs Historis

| File | Status | Keterangan |
|------|--------|------------|
| [`01_PRD.md`](./01_PRD.md) | 🔶 Sebagian historis | PRD v1 (PDF-first, 02-08-2026). Scope aktual lebih luas — lihat catatan di file. |
| [`02_GOALS_AND_SCOPE.md`](./02_GOALS_AND_SCOPE.md) | 🔶 Sebagian historis | Masih menyebut Streamlit & PDF-only; sudah diperbaiki 2026-08-09. |
| [`03_TECHNICAL_SPECIFICATION.md`](./03_TECHNICAL_SPECIFICATION.md) | ❌ **HISTORIS** | Spec stack lama (Streamlit, GPTCache, LangChain 0.1, chromadb 0.4.22). JANGAN diikuti. |
| [`04_ARCHITECTURE_AND_WORKFLOW.md`](./04_ARCHITECTURE_AND_WORKFLOW.md) | ❌ **HISTORIS** | Diagram arsitektur Streamlit + GPTCache. JANGAN diikuti. |
| [`05_DEVELOPMENT_FLOW.md`](./05_DEVELOPMENT_FLOW.md) | ✅ Development log | Log sprint yang sudah di-update ke stack aktual (React/Bun, cache custom). |
| [`06_ROADMAP.md`](./06_ROADMAP.md) | ✅ Aktual | Roadmap per 07-08-2026. |
| [`07_TESTING_AND_QA.md`](./07_TESTING_AND_QA.md) | 🔶 Sebagian aktual | Checklist lama; status verifikasi audit 2026-08-09 ditambahkan. |
| [**`.agents/`**](../.agents/README.md) | ✅ **KANONIK** | Handover pack resmi — stack aktual, arsitektur, perintah build/run, roadmap. **Baca ini dulu.** |
