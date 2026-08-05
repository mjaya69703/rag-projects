# 03 — Windows Quirks & Workaround (WAJIB TAHU)

Semua terkonfirmasi di mesin dev. Kalau ada hang/error aneh di Windows, cek daftar
ini dulu.

## 1. PyMuPDF: `doc[-1]` pada dokumen kosong → HANG selamanya
`fitz.open()` lalu akses `doc[-1]` saat `page_count == 0` **menggantung tanpa
error** (bukan IndexError). Workaround: cek `doc.page_count` atau panggil
`doc.new_page()` dulu (lihat `tests/make_sample_pdf.py::_add_block`).

## 2. ChromaDB: file lock sampai `close()`
Di Windows, file `data_level0.bin` tetap di-lock oleh proses sampai
`client.close()` dipanggil. Wajib `store.close()` sebelum menghapus/merapikan
direktori, dan `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` di test.
Sudah ditangani via `VectorStore.close()`.

## 3. SQLite: `PRAGMA foreign_keys` default OFF
`ON DELETE CASCADE` TIDAK bekerja tanpa `PRAGMA foreign_keys = ON` di tiap
koneksi. `app/db.py::_conn()` sudah mengaktifkannya. Jangan hapus.

## 4. HuggingFace cache: peringatan symlinks (tidak fatal)
Warning "cache-system uses symlinks... degraded version" muncul karena Windows
tanpa Developer Mode. Aman diabaikan; bisa di-set `HF_HUB_DISABLE_SYMLINKS_WARNING=1`.

## 5. cmd.exe quirks
- Shell aktif adalah `cmd.exe`, bukan bash. Dilarang heredoc/`$()`/`&&`-bash-ism
  selain yang didukung cmd. Gunakan dedicated tools (read/edit/write) untuk file.
- `python` di PATH = global Python 3.14. Selalu pakai venv: `.venv\Scripts\python`.

## 6. GPTCache auto-install rusak
GPTCache 0.1.44 saat runtime meng-klaim "successfully installed faiss-cpu" padahal
gagal — jangan pernah bergantung pada GPTCache (sudah dihapus dari requirements).

## 7. venv & pip
Venv di `.venv`. Install dependency baru selalu via `.venv\Scripts\pip install`.

## 8. File bernama `nul` / `aux` (reserved device names)
Di cmd.exe, `> nul` kadang tidak sengaja membuat FILE bernama `nul` di folder kerja
(pernah terjadi di repo ini, 06-08-2026). File ini tidak bisa dihapus dengan
`del nul` biasa. Cara hapus:
```powershell
Remove-Item -LiteralPath '\\?\c:\wumpus\www\rag-projects\nul' -Force
```
Jangan buat file dengan nama device reserved (nul, aux, con, prn, com1-9, lpt1-9).
