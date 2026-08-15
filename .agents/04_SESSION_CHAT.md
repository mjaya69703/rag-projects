# 04 — Multi-Session Chat (Sprint 4-5 bonus)

Fitur lengkap: beberapa sesi chat independen & persistent (SQLite), seperti
ChatGPT/Claude. Diimplementasi 2026-08-02. Semua test hijau (26 pytest).

## Schema (app/db.py)
- `sessions(id TEXT PK, title, created_at, updated_at)` — sorted by updated_at DESC
- `messages(id INTEGER PK AUTOINCREMENT, session_id FK, role check user/assistant,
  content, sources TEXT JSON, created_at)`
- `session_summaries(session_id PK, summary_text, last_message_index, created_at)`
- FK cascade aktif (`PRAGMA foreign_keys=ON`) — delete session hapus pesan juga.

## API
- `POST /sessions/create` → `{session: {id, title, ...}}`
- `GET /sessions/list` → sessions sorted updated_at DESC
- `GET /sessions/{id}/messages` → semua pesan (sources di-parse dari JSON)
- `PUT /sessions/{id}/rename` `{title}` → rename
- `DELETE /sessions/{id}` → hapus session + pesan
- `POST /query` body tambahan: `{session_id?, mode: "sliding"|"summary",
  history_n?}` → response tambah `session: {id, title, messages, tokens_est,
  over_token_warning, mode}`

## Strategi konteks
- **sliding**: `get_messages(limit=history_n)` default 15 → seluruhnya masuk prompt.
- **summary**: ringkasan tersimpan (diletakkan sebagai pesan system di dalam
  history) + `get_messages(limit=5)`.
- History non-empty → **cache semantic di-skip** (jawaban tergantung konteks).
- Jika session_id tidak ada di DB → 404.

## Auto-title & summary
- Pesan pertama di session (title masih "New Chat") → `engine.generate_title()`
  (LLM, ≤5 kata, max_tokens 30, fallback "New Chat").
- Setiap `message_count % 10 == 0` → `engine.summarize()` (LLM, ≤150 kata) →
  simpan ke `session_summaries` (hanya jika last_message_index belum update).

## Token tracking
- `estimate_tokens()` = total chars/4. `TOKEN_WARNING = 4000`.
- UI menampilkan warning jika `over_token_warning`; saran: mode summary / new chat.

## UI (React SPA, `frontend/src/`)
> Catatan (2026-08-09): UI asli Streamlit (`ui.py`) sudah diganti SPA React 19 + Vite + Bun
> sejak Sprint 5 — deskripsi di bawah mencerminkan implementasi React saat ini.

- Sidebar (`components/Sidebar.tsx`): tombol `➕ New Chat`, daftar session, rename, delete dengan `ConfirmDialog`, upload dokumen & dokumen manager.
- Main (`pages/Chat.tsx`): riwayat di-render dari API (`GET /sessions/{id}/messages`) + streaming SSE (`POST /query/stream`, event `meta`/`delta`/`done`/`error`); composer selalu tampil; kalau backend mati → error-state koneksi dengan retry, tidak crash.
- Auto-create session pertama saat app dibuka (kalau API hidup).
- Mode konteks (sliding/summary) & top-k & filter source dari floating composer strip.
