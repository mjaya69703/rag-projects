# Backup & Restore (P2-08)

State knowledge base berada di 3 lokasi yang HARUS di-backup bersama agar
konsisten:

| Lokasi | Isi |
|---|---|
| `data/chroma_db/` | Indeks vektor (ChromaDB) |
| `data/chat.db` | SQLite: session, pesan, anotasi, kartu belajar, registry dokumen |
| `uploads/` | Dokumen sumber asli |

## Perintah

```bat
:: Backup (arsip zip timestamped + manifest sha256)
.venv\Scripts\python deploy\backup_restore.py backup

:: Daftar backup + ukuran
.venv\Scripts\python deploy\backup_restore.py list

:: Validasi arsip (sha256 semua file + PRAGMA integrity_check SQLite)
.venv\Scripts\python deploy\backup_restore.py verify backups\rag-backup-YYYYMMDD-HHMMSS.zip

:: Pulihkan (state lama digeser ke .pre-restore-<ts>, tidak langsung dihapus)
.venv\Scripts\python deploy\backup_restore.py restore backups\rag-backup-YYYYMMDD-HHMMSS.zip
```

Argumen opsional: `--root <dir>` (root proyek), `--out-dir <dir>`
(folder backup, default `<root>/backups`), `--keep N` (retensi: hapus
backup terlama selain N terbaru, default 5).

## Otomasi (Windows Task Scheduler / cron)

Jadwalkan harian, mis. lewat Task Scheduler:

```
Program:  C:\wumpus\www\rag-projects\.venv\Scripts\python.exe
Arguments: C:\wumpus\www\rag-projects\deploy\backup_restore.py backup
Start in: C:\wumpus\www\rag-projects
```

## Prosedur restore yang aman

1. Hentikan service (`stop` service / tutup `run_dev.py`).
2. `verify` arsip dulu — jangan restore arsip yang gagal verifikasi.
3. Jalankan `restore <arsip>`. State lama digeser ke
   `<root>/.pre-restore-<ts>` — jangan dihapus sampai app terbukti sehat.
4. Restart service. Cek `/health` dan daftar dokumen di UI.
5. Hapus `.pre-restore-*` secara manual setelah yakin.

## Catatan

- SQLite di-backup lewat `sqlite3.Connection.backup()` sehingga konsisten
  walau database sedang dipakai.
- Arsip berisi `manifest.json` (versi schema, daftar file + sha256).
  Script menolak arsip yang mencurigakan (zip-slip / path traversal).
- `data/` dan `uploads/` di-ignore git — backup ini satu-satunya salinan
  state; simpan folder `backups/` di luar mesin (drive eksternal/cloud).
