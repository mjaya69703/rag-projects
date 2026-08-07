# Custom Frontend Handover (React 19 + Vite + Bun)

Updated 07-08-2026.

Frontend aplikasi Knowledge Base ini adalah Single Page Application (SPA) berbasis **React 19 + Vite + React Router** yang dikelola menggunakan **Bun**.

## Alur Build & Serving

1. Source code frontend berada di folder `frontend/`.
2. Hasil build di-output ke `app/static/` via Vite (`outDir: '../app/static'`).
3. Backend FastAPI (`app/main.py`) menyajikan file statis dari `app/static/` di route `/` dan menangani SPA fallback (semua route non-API dialihkan ke `index.html`).

## Perintah Build Wajib

```cmd
cd frontend
bun install

# Development server dengan hot-reload (proxy API ke 127.0.0.1:8000):
bun run dev

# Production build ke app/static/:
bun run build
```

## Struktur Halaman Frontend (`frontend/src/pages/`)

- `Chat.tsx`: Interface percakapan RAG dengan streaming SSE, empty state hero banner dengan chip contoh pertanyaan, floating composer strip (filter dokumen, mode konteks, top-k), serta typing dots indicator.
- `Library.tsx`: Manajemen koleksi dokumen, stat KPI cards, interactive chunk inspector (dengan editor anotasi), serta hub pembelajaran.
- `Quiz.tsx`: Pembuat soal interaktif dari dokumen, opsi pilihan ganda `A/B/C/D`, koreksi otomatis + penjelasan LLM, banner loading evaluasi AI, dan riwayat skor.
- `Flashcards.tsx`: Stage kartu belajar 3D (*CSS 3D perspective flip*), progress penguasaan materi, dan tombol evaluasi "Belum Tahu" / "Sudah Tahu".
- `Progress.tsx`: Learning Analytics Dashboard dengan KPI stat grid, cakupan bab per dokumen, dan matriks area lemah.
- `Settings.tsx`: Control panel tema (Dark/Light mode), live metrik kesehatan sistem & *Semantic Cache Hit Rate*, serta perintah integrasi MCP Server & Bot Telegram.

## Konvensi UI & Modals

1. **100% Kustom Modal React (Tanpa Modal Bawaan Browser)**:
   - Gunakan `<ConfirmDialog>` untuk konfirmasi hapus (menggantikan `window.confirm()`).
   - Gunakan `<PromptDialog>` untuk input teks/catatan (menggantikan `window.prompt()`).
   - Dilarang keras memanggil `confirm()`, `prompt()`, atau `alert()` bawaan browser.
2. **Standard Indikator Loading**:
   - Semua tombol async wajib menampilkan `.spinner` dan masuk ke state `disabled` saat request berjalan.
   - Gunakan `typing-dots` pada pesan balasan assistant saat menunggu token stream pertama.
