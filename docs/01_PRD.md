# Product Requirements Document (PRD)
**Nama Proyek:** Personal AI Knowledge Base (RAG)
**Versi:** 1.0
**Tanggal:** 02 Agustus 2026

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