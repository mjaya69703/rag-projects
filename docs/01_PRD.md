# Product Requirements Document (PRD)
**Nama Proyek:** Personal AI Knowledge Base (RAG)
**Versi:** 1.0
**Tanggal:** 02 Agustus 2026

> ⚠️ **DOKUMEN HISTORIS (sebagian)** — PRD ini ditulis untuk scope v1 (PDF-first, 02-08-2026) dan masih berlaku sebagai catatan kebutuhan awal. Scope aktual sudah jauh lebih luas (multi-format, React 19 SPA, hybrid search, 15 fitur learning loop). **Untuk stack & arsitektur aktual, lihat [`.agents/README.md`](../.agents/README.md) sebagai referensi kanonik.**

> 📌 **Pembaruan scope (2026-08-09):** Sejak PRD v1 ditulis, hal-hal berikut sudah bertambah/diimplementasikan: (1) format input diperluas ke MD/TXT/DOCX/PPTX/HTML/URL + Watch-Folder; (2) UI diganti dari rencana sederhana menjadi SPA React 19 + Vite + Bun dengan SSE streaming; (3) pencarian menjadi hybrid (BM25 + vector), bukan vector-only; (4) semantic cache diimplementasikan custom di ChromaDB (bukan GPTCache); (5) ditambahkan multi-session chat persistent, MCP Server, Bot Telegram, dan 15 fitur Learning Loop.

## 1. Latar Belakang
Pengguna membutuhkan cara cepat untuk mencari dan memahami informasi dari tumpukan dokumen PDF (materi kuliah, presentasi kantor). Pencarian keyword tradisional (Ctrl+F) tidak efektif karena tidak memahami konteks semantik.

## 2. Masalah yang Diselesaikan
- Kesulitan mencari informasi spesifik di dalam ratusan halaman PDF.
- AI LLM standar sering berhalusinasi jika ditanya tentang dokumen pribadi.
- Keterbatasan resource server (RAM 8GB total di Proxmox).

## 3. Solusi yang Ditawarkan
Sistem RAG yang:
- Mengindeks dokumen secara semantik menggunakan Embedding Model lokal yang ringan.
- Menggunakan API LLM eksternal hanya untuk proses *generation* jawaban.
- Menjalankan seluruh backend di dalam 1 LXC ringan (Ubuntu/Debian).

## 4. User Persona
- **Pengguna:** Mahasiswa STI / Profesional IT yang memiliki banyak dokumen referensi.
- **Kebutuhan:** Akses cepat, akurat, dan bisa dari mana saja (mobile-friendly).

## 5. Kebutuhan Fungsional
| ID | Fitur | Prioritas | Deskripsi |
|----|-------|-----------|-----------|
| F1 | Upload PDF | High | User bisa upload file PDF via UI. |
| F2 | Smart Chunking | High | PDF dipotong berdasarkan heading/bab, bukan potong paksa. |
| F3 | Chat Interface | High | UI chat untuk bertanya tentang dokumen. |
| F4 | Source Citation | Medium | Jawaban AI menyebutkan sumber (file & halaman). |
| F5 | Semantic Cache | Medium | Cache jawaban untuk pertanyaan yang mirip. |
| F6 | Remote Access | High | Akses via Cloudflare Tunnel dengan autentikasi. |

## 6. Kebutuhan Non-Fungsional
- **Performance:** Respon chat < 5 detik.
- **Resource:** Total RAM usage < 1.5 GB saat idle.
- **Security:** Endpoint harus dilindungi Cloudflare Access.
- **Language:** Support Bahasa Indonesia & Inggris.