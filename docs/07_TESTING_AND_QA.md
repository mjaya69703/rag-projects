# Testing & QA Guide

> 📌 **Status verifikasi (2026-08-09, berdasar [`.docs/PROJECT_AUDIT_2026-08-09.md`](../.docs/PROJECT_AUDIT_2026-08-09.md)):**
> - ✅ Subset parser/database/ingestion: **47 test pass** (dengan `--basetemp .pytest-tmp`) — diverifikasi ulang saat audit.
> - ⚠️ Suite API: **belum dapat dinyatakan pass** di environment audit (gagal saat model embedding mencoba akses Hugging Face).
> - ⚠️ Frontend build (`bun run build`): **belum dapat dinyatakan pass** di environment audit (EPERM membuka `frontend/node_modules/picomatch/index.js`).
> - ❌ Belum ada: browser E2E (upload→query→citation→delete, session, learning), security tests (SSRF/auth), latency & RAM benchmark, LLM tests penuh.
> - Checklist di bawah mencerminkan rencana QA historis; jangan menganggap item yang masih unchecked sebagai sudah terverifikasi.

## 🧪 Testing Strategy

### 1. Unit Testing (Per Modul)
**PDF Parser:** *(status: 02-08-2026, Sprint 1 ✔)*
- [x] Test baca PDF text-based — `tests/test_pipeline.py::test_parse_pdf` (via `extract_pages`)
- [x] Test extract metadata (page number) — nomor halaman 1-based, di-assert di test
- [x] Test smart chunking (cek apakah chunk sesuai heading) — heading `2.1 Pengertian VLAN`, `Bab 4: Troubleshooting`, dll. terdeteksi dari font size
- [ ] Test overlap antar chunk — overlap aktif (`chunk_overlap=50`), assertion eksplisit belum dibuat

**Vector Store:**
- [x] Test init ChromaDB — `tests/test_pipeline.py::test_vector_store`
- [x] Test add documents — 20 chunk tersimpan, `count()` cocok
- [x] Test search (cek apakah return chunk yang relevan) — query "Apa itu VLAN?" → top-1 section `2.2 Manfaat VLAN` (distance ~0.24)
- [x] Test delete documents — `delete_document()` + `count() == 0`

**LLM Client:** *(Sprint 2)*
- [ ] Test API call (cek response format)
- [ ] Test error handling (API down, timeout)
- [ ] Test prompt construction

### 2. Integration Testing (End-to-End)
**Upload Flow:** *(status: 02-08-2026, Sprint 1 ✔ — via CLI, UI belum ada)*
1. [x] Upload PDF "Materi_Jaringan.pdf" — sample di-index via `python ingest.py uploads\materi_jaringan.pdf`
2. [x] Cek di ChromaDB: apakah dokumen terindeks? — `list_documents()` → `materi_jaringan.pdf`, 20 chunk
3. [x] Cek metadata: apakah source & page benar? — source = nama file, page = 1 (benar)

**Query Flow:**
1. Tanya: "Apa itu VLAN?"
2. Cek jawaban: apakah relevan dengan dokumen?
3. Cek source: apakah menyebutkan file & halaman?
4. Cek cache: tanya lagi pertanyaan yang sama, apakah dari cache?

### 3. Performance Testing
**Latency:**
- [ ] Query pertama (no cache): <5 detik
- [ ] Query kedua (cached): <1 detik
- [ ] Upload PDF 50 halaman: <30 detik

**Resource Usage:**
- [ ] RAM usage saat idle: <500 MB
- [ ] RAM usage saat query: <1 GB
- [ ] CPU usage saat indexing: <80% (tidak bikin LXC hang)

### 4. Security Testing
- [ ] Akses tanpa Cloudflare Access → ditolak
- [ ] Akses dengan email yang di-allow → diterima
- [ ] API key tidak terekspos di frontend
- [ ] File upload dibatasi (max size; validasi ekstensi: PDF, MD, TXT, DOCX, PPTX, HTML, URL)
- [ ] SSRF protection pada ingest URL (blokir IP private/loopback/metadata, validasi redirect) — *in progress (2026-08-09), lihat audit P0-01*
- [ ] Auth aplikasi (token) → endpoint mutasi/data menolak request tanpa kredensial — *in progress (2026-08-09), lihat audit P0-02*

## 🐛 Common Issues & Solutions

### Issue 1: Chunking terpotong di tengah kalimat
**Solusi:** Pastikan `RecursiveCharacterTextSplitter` pakai separator yang benar:
```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

### Issue 2: Jawaban AI tidak relevan
Solusi:
Cek apakah Top-K terlalu kecil (naikkan ke 5)
Cek apakah embedding model cocok untuk bahasa dokumen
Perbaiki system prompt agar lebih ketat
### Issue 3: RAM usage tinggi
Solusi:
Pastikan embedding model di-load sekali (global variable)
Batasi ukuran PDF yang bisa diupload (max 50MB)
Hapus dokumen yang tidak dipakai dari ChromaDB
## Issue 4: Cloudflare Tunnel tidak connect
Solusi:
Cek status cloudflared service: systemctl status cloudflared
Cek log: journalctl -u cloudflared -f
Pastikan tunnel token valid
## ✅ Pre-Deployment Checklist
- Semua unit test pass
- Integration test pass
- Performance test pass (latency & RAM)
- Security test pass (Cloudflare Access working)
- .env file configured (API key, DB path)
- Systemd service created & enabled
- Documentation updated