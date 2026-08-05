# Personal AI Knowledge Base (RAG System)

## 📌 Deskripsi Singkat
Sistem *Retrieval-Augmented Generation* (RAG) pribadi yang memungkinkan pengguna mengunggah dokumen (PDF materi kuliah, presentasi kantor), lalu melakukan tanya-jawab dengan AI berdasarkan konteks dari dokumen tersebut. Sistem ini dioptimasi untuk berjalan di *resource-constrained environment* (LXC dengan RAM 2-3GB) dan menggunakan API LLM eksternal untuk efisiensi.

## 🎯 Tujuan Utama
Menyediakan "Otak Kedua" (*Second Brain*) yang dapat diakses dari mana saja, mampu memahami dokumen berbahasa Indonesia dan Inggris, serta hemat penggunaan token API.

## 🚀 Fitur Utama
1. **Upload Dokumen:** Mendukung PDF dengan *smart chunking* (berdasarkan struktur/bab).
2. **Chat Interface:** UI sederhana untuk bertanya tentang dokumen yang sudah diunggah.
3. **Source Tracking:** AI akan menyebutkan dari halaman/file mana jawaban diambil.
4. **Semantic Cache:** Menghemat token API dengan menyimpan jawaban dari pertanyaan yang mirip.
5. **Akses Remote:** Diakses via Cloudflare Tunnel dengan autentikasi Zero Trust.

## 📚 Dokumentasi Lengkap
- [PRD](./01_PRD.md)
- [Goals & Scope](./02_GOALS_AND_SCOPE.md)
- [Technical Specification](./03_TECHNICAL_SPECIFICATION.md)
- [Architecture & Workflow](./04_ARCHITECTURE_AND_WORKFLOW.md)
- [Development Flow](./05_DEVELOPMENT_FLOW.md)
- [Roadmap](./06_ROADMAP.md)
- [Testing & QA](./07_TESTING_AND_QA.md)