# Deploy RAG Knowledge Base ke Ubuntu/Debian LXC

Panduan deploy proyek ini ke container LXC (Ubuntu/Debian, RAM 2–3 GB) yang
dilindungi **Cloudflare Tunnel + Cloudflare Access**.

## Arsitektur target

```
Internet ──> Cloudflare Access (email allowlist) ──> cloudflared (tunnel, di LXC)
                                                          │
                                                    127.0.0.1:8000
                                                          │
                                              FastAPI + ChromaDB + MiniLM
                                              (satu proses, satu service systemd)
```

- UI (SPA statis) **disajikan oleh FastAPI di :8000** — tidak ada frontend/web
  server terpisah (tidak ada port 3000).
- Service hanya bind ke `127.0.0.1:8000`. Cloudflare Tunnel (`cloudflared`)
  adalah satu-satunya jalan keluar ke publik.
- Aplikasi **tidak punya autentikasi sendiri** — Cloudflare Access adalah
  satu-satunya gerbang (cocok untuk pemakaian single-user).

## Prasyarat

- LXC container Ubuntu (22.04/24.04) atau Debian (12+), RAM 2–3 GB, disk ≥10 GB.
- Akses internet keluar dari container (untuk: download model HF ~130 MB,
  panggilan LLM API, koneksi Cloudflare).
- Sebuah domain yang nameserver-nya di-manage Cloudflare (mis. `example.com`).
- Akun Cloudflare (free tier cukup).
- Kode proyek ini (bisa di-copy via `scp` dari mesin Windows, atau `git clone`).

---

## Step 1 — Install cloudflared di LXC (Quick Tunnel)

**Token didapat dari dashboard Zero Trust:**

1. Login ke Cloudflare → **Zero Trust** → **Networks → Tunnels** →
   **Create a tunnel** → pilih tipe **Cloudflared**.
2. Di langkah *Install and run a connector*, dashboard menampilkan perintah
   install beserta **token** (string panjang `eyJhIjoi...`). Salin token itu.
3. Di dalam LXC (sebagai root):

   ```bash
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
   dpkg -i cloudflared.deb

   # Pasang & jalankan cloudflared sebagai service systemd:
   cloudflared service install <TOKEN>
   ```

   Perintah `service install` membuat service `cloudflared` dan langsung
   menghubungkan container ke tunnel. Cek: `systemctl status cloudflared`.

4. Kembali ke dashboard tunnel, tab **Public Hostname** → **Add a public
   hostname**:
   - Subdomain/domain: mis. `kb.example.com`
   - Service: **HTTP** → URL: `localhost:8000`

   Simpan. Tunnel sekarang meneruskan trafik `kb.example.com` →
   `127.0.0.1:8000` di container.

> Alternatif tanpa paket .deb: ikuti saja perintah install yang ditampilkan
> dashboard (biasanya `curl -L ... | tar xz` lalu `./cloudflared service
> install <TOKEN>`).

## Step 2 — Cloudflare Access: batasi hanya email Anda

Aplikasi RAG ini **tidak punya login sendiri** — siapa pun yang tahu URL bisa
upload PDF dan bertanya. Maka Access WAJIB dipasang.

1. Zero Trust → **Access → Applications** → **Add an application** →
   **Self-hosted**.
2. Application domain: `kb.example.com` (sama dengan public hostname di Step 1).
3. Buat policy:
   - Action: **Allow**
   - Include: **Emails** → masukkan **email Anda** (hanya satu).
   - Simpan.
4. Tes dari browser lain / mode incognito: harus diminta login (email OTP), dan
   email selain milik Anda ditolak.

> Karena hanya ada satu pengguna, email allowlist cukup. Jangan menambah
> *Anyone* / *Everyone* ke policy ini.

## Step 3 — Deploy aplikasi

1. Masukkan kode ke container (dari mesin Windows):

   ```bash
   scp -r rag-projects root@<ip-lxc>:~/
   ```

2. Jalankan script install (sebagai root; argumen = path ke repo):

   ```bash
   bash ~/rag-projects/deploy/install_lxc.sh ~/rag-projects
   ```

   Script melakukan: buat user `rag` → install paket sistem → salin kode ke
   `/opt/rag` → buat `.venv` + `pip install` (torch CPU-only, tanpa CUDA) →
   buat `.env` dari `.env.example` → buat `data/` & `uploads/` → pasang &
   jalankan service `rag-backend`.

   > Idempotent: aman dijalankan ulang. `data/`, `uploads/`, `.env` tidak
   > ditimpa.

3. Isi konfigurasi:

   ```bash
   nano /opt/rag/.env
   ```

   | Variabel        | Wajib | Default                    | Keterangan |
   |-----------------|-------|----------------------------|------------|
   | `LLM_API_KEY`   | Ya    | —                          | API key LLM eksternal (OpenAI-compatible) |
   | `LLM_API_BASE`  | Ya    | `https://api.openai.com/v1`| Base URL API (boleh provider lain, mis. `https://api.deepseek.com/v1`) |
   | `LLM_MODEL`     | Ya    | —                          | Nama model, mis. `gpt-4o-mini` / `deepseek-chat` |
   | `PERSIST_DIR`   | Tidak | `data/chroma_db`           | Folder ChromaDB (relatif ke `/opt/rag`) |
   | `UPLOAD_DIR`    | Tidak | `uploads`                  | Folder PDF upload |
   | `DB_PATH`       | Tidak | `data/chat.db`             | SQLite session/chat |
   | `RAG_MAX_TOKENS`| Tidak | `1024`                     | Batas token jawaban LLM |
   | `LOG_DIR`       | Tidak | *(kosong)*                | Folder log file (RotatingFileHandler); kosong = log ke console saja |
   | `CORS_ORIGINS`  | Tidak | `localhost/127.0.0.1:3000,8000` | Whitelist origin CORS (koma); `*` = semua (tanpa credentials) |
   | `RATE_LIMIT_QPM`| Tidak | `30`                      | Rate limit per menit per IP utk `/query` & `/upload`; `0` = nonaktif |

   Contoh minimal:

   ```bash
   LLM_API_KEY=sk-xxxx
   LLM_API_BASE=https://api.deepseek.com/v1
   LLM_MODEL=deepseek-chat
   ```

4. Restart service:

   ```bash
   systemctl restart rag-backend
   ```

## Step 4 — Verifikasi

```bash
# Status service
systemctl status rag-backend

# Health check lokal (harusnya: {"status":"ok"})
curl -s http://127.0.0.1:8000/health

# Log real-time
journalctl -u rag-backend -f
```

Lalu buka `https://kb.example.com` di browser → upload PDF pertama.

> **Catatan:** model embedding MiniLM (`paraphrase-multilingual-MiniLM-L12-v2`)
> di-download **pada upload/query pertama** (~130 MB, lazy-load), bukan saat
> service start. Upload pertama bisa terasa lambat — tunggu sampai selesai.
> Cache model tersimpan di `/home/rag/.cache/huggingface`.

## Catatan keamanan

- **Jangan pernah expose port 8000 ke publik.** Service bind `127.0.0.1`
  (sudah diatur di unit systemd). Kalau perlu firewall di host LXC
  (contoh UFW):

  ```bash
  ufw allow 22/tcp        # SSH
  ufw allow 7844/udp      # (opsional) QUIC cloudflared
  ufw default deny incoming
  ufw enable
  ```

- Akses publik **hanya** lewat Cloudflare Access (Step 2). Tanpa itu, aplikasi
  terbuka untuk siapa saja.
- Tidak perlu GPU dan tidak perlu OCR — murni CPU. `torch` diinstall versi
  CPU-only oleh script install.
- RAM: idle <500 MB, saat query ~1 GB (MiniLM + ChromaDB in-process).
  Unit systemd memakai `MemoryMax=1536M`; kalau LXC diberi RAM lebih
  (mis. 4 GB), naikkan nilai itu di `/etc/systemd/system/rag-backend.service`
  lalu `systemctl daemon-reload && systemctl restart rag-backend`.
- Jangan commit `.env` ke git.

## Upgrade aplikasi

1. Tarik kode terbaru / salin ulang repo ke container.
2. Jalankan ulang script install (idempotent, data aman):

   ```bash
   bash ~/rag-projects/deploy/install_lxc.sh ~/rag-projects
   ```

   > Script menyalin ulang kode tapi **tidak me-restart** service yang sedang
   > berjalan. Setelah selesai, restart manual:
   > `systemctl restart rag-backend`
   >
   > Catatan: file yang sudah tidak ada di repo tidak dihapus dari `/opt/rag`.
   > Kalau butuh bersih total, backup `data/` & `uploads/`, hapus `/opt/rag`,
   > lalu install ulang.

3. **Jika model embedding diganti** (bukan cuma kode) → vektor lama tidak
   kompatibel, wajib reset & re-index + clear cache (jalankan dari `/opt/rag`
   sebagai user `rag`):

   ```bash
   sudo -u rag /opt/rag/.venv/bin/python -c "from app.vector_store import VectorStore; from app.semantic_cache import SemanticCache; s=VectorStore(); s.reset(); SemanticCache(s).clear(); s.close()"
   sudo -u rag /opt/rag/.venv/bin/python ingest.py uploads/<file> --source "X" --replace
   ```

   (Ulangi baris `ingest.py` untuk tiap PDF, atau upload ulang lewat UI.)

## Troubleshooting

**Port 8000 sibuk / service gagal bind**

```bash
ss -tlnp | grep 8000
```

Matikan proses lain yang memakai 8000, atau ubah port di unit
(`/etc/systemd/system/rag-backend.service`) lalu `daemon-reload` + restart
(jangan lupa sesuaikan juga Service URL di Public Hostname tunnel).

**Service restart loop / OOM-kill (MemoryMax)**

Cek di log:

```bash
journalctl -u rag-backend | grep -iE "oom|killed"
dmesg | grep -i oom
```

Naikkan `MemoryMax` di unit (mis. `2560M`) atau tambah swap di LXC, lalu
`systemctl daemon-reload && systemctl restart rag-backend`.

**Error "database is locked" / ChromaDB lock setelah kill paksa**

Terjadi kalau proses di-kill paksa (SIGKILL/`kill -9`). Unit memakai
`KillSignal=SIGINT` supaya shutdown graceful dan ini jarang terjadi, tapi kalau
muncul:

```bash
systemctl stop rag-backend
pgrep -af uvicorn || true      # pastikan tidak ada proses tersisa
systemctl start rag-backend
```

**Service hidup tapi jawaban 502 / LLM error**

`.env` salah: cek `LLM_API_KEY` / `LLM_API_BASE` / `LLM_MODEL` di
`/opt/rag/.env`, lalu `systemctl restart rag-backend`. Cek log
`journalctl -u rag-backend -f` untuk detail error dari LLM API.

**Download model HF gagal / ingin tes manual**

```bash
sudo -u rag /opt/rag/.venv/bin/python -c "from app.vector_store import _get_model; _get_model()"
```

Error jaringan/proxy akan tampil di sini.
