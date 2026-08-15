#!/usr/bin/env bash
# =============================================================================
# install_lxc.sh — Setup otomatis backend RAG di Ubuntu/Debian LXC.
#
# Cara pakai (jalankan sebagai root, dari dalam repo atau beri path repo):
#   bash deploy/install_lxc.sh /path/ke/repo
#   bash deploy/install_lxc.sh            # default: salin direktori saat ini
#
# Idempotent — aman dijalankan ulang:
#   - Kode disalin ulang ke /opt/rag (file yang sudah tidak ada di repo
#     TIDAK dihapus dari /opt/rag)
#   - data/, uploads/, .env TIDAK ditimpa/dihapus
# =============================================================================
set -euo pipefail

APP_DIR="/opt/rag"
SERVICE="rag-backend"
SRC="${1:-$(pwd)}"

RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; BOLD=$'\e[1m'; RESET=$'\e[0m'

info()  { echo -e "${GREEN}[INFO]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET} $*"; }
err()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
banner(){ echo -e "\n${BOLD}===== $* =====${RESET}\n"; }

# --- Prasyarat: root + sumber repo valid -------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    err "Jalankan sebagai root:  sudo bash deploy/install_lxc.sh <path-ke-repo>"
    exit 1
fi

if [ ! -d "$SRC/app" ] || [ ! -f "$SRC/requirements.txt" ]; then
    err "Sumber repo tidak ditemukan di: $SRC"
    err "Jalankan dari root repo, atau beri argumen path repo:"
    err "  bash deploy/install_lxc.sh /home/user/rag-projects"
    exit 1
fi
SRC="$(cd "$SRC" && pwd)"   # jadikan absolut

# --- 1/7 User 'rag' ----------------------------------------------------------
banner "1/7 User sistem 'rag'"
if id "rag" &>/dev/null; then
    info "User 'rag' sudah ada — dilewati."
else
    useradd -m -s /bin/bash rag
    info "User 'rag' dibuat (home /home/rag)."
fi

# --- 2/7 Paket sistem --------------------------------------------------------
banner "2/7 Install paket sistem (python3-venv, pip, curl, unzip, git)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-pip curl unzip git

# --- 3/7 Salin kode ke /opt/rag ----------------------------------------------
banner "3/7 Salin kode ke $APP_DIR"
mkdir -p "$APP_DIR"
if [ "$SRC" != "$APP_DIR" ]; then
    # Salin TANPA artefak yang tidak berguna/berbahaya di Linux:
    #   .git, .venv (venv Windows tidak jalan di Linux), .env (rahasia),
    #   data/ uploads/ (data runtime lama), __pycache__, .pytest_cache,
    #   node_modules, .hallmark, .docs, .vscode, .pytest-tmp
    tar -C "$SRC" \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='node_modules' \
        --exclude='.env' \
        --exclude='data' \
        --exclude='uploads' \
        --exclude='__pycache__' \
        --exclude='.pytest_cache' \
        --exclude='.pytest-tmp' \
        --exclude='.hallmark' \
        --exclude='.docs' \
        --exclude='.vscode' \
        -cf - . | tar -C "$APP_DIR" -xf -
    info "Kode disalin dari $SRC."
else
    info "Sumber = $APP_DIR — tidak perlu menyalin."
fi

# --- 4/7 Virtualenv + dependencies -------------------------------------------
banner "4/7 Virtualenv & install dependencies (tahap paling lama)"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/.venv"
    info "Virtualenv dibuat."
else
    info "Virtualenv sudah ada."
fi

# Cache pip dimatikan agar disk LXC tidak bengkak (wheel torch besar).
export PIP_NO_CACHE_DIR=1

"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip

# Torch CPU-only: index PyPI default mengunduh wheel CUDA (>2 GB, butuh GPU).
# LXC ini tanpa GPU, jadi pakai index resmi CPU (~200 MB).
"$APP_DIR/.venv/bin/python" -m pip install torch \
    --index-url https://download.pytorch.org/whl/cpu

"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

# Pastikan seluruh /opt/rag (termasuk .venv) dimiliki user 'rag'.
chown -R rag:rag "$APP_DIR"

# --- 5/7 .env ----------------------------------------------------------------
banner "5/7 Konfigurasi .env"
if [ -f "$APP_DIR/.env" ]; then
    info ".env sudah ada — tidak ditimpa."
else
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chown rag:rag "$APP_DIR/.env"
    warn "================================================================"
    warn "  .env BARU dibuat dari .env.example."
    warn "  WAJIB DIISI sebelum dipakai:"
    warn "    nano $APP_DIR/.env"
    warn "    LLM_API_KEY=sk-...."
    warn "    LLM_API_BASE=https://api.openai.com/v1   (atau provider lain)"
    warn "    LLM_MODEL=gpt-4o-mini                    (atau model anda)"
    warn "  Lalu restart: systemctl restart rag-backend"
    warn "================================================================"
fi

# --- 6/7 Direktori data & uploads --------------------------------------------
banner "6/7 Direktori data & uploads"
mkdir -p "$APP_DIR/data" "$APP_DIR/uploads" "$APP_DIR/data/logs"
chown -R rag:rag "$APP_DIR/data" "$APP_DIR/uploads"
info "data/, data/logs/, uploads/ siap (writable oleh user 'rag')."

# --- 7/7 Systemd unit --------------------------------------------------------
banner "7/7 Pasang systemd unit & nyalakan service"
cp "$APP_DIR/deploy/rag-backend.service" "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable --now "$SERVICE"
info "Service '$SERVICE' terpasang & aktif."

# --- Verifikasi cepat --------------------------------------------------------
sleep 3
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    info "Health check OK -> http://127.0.0.1:8000/health"
else
    warn "Health check belum OK (kemungkinan .env belum diisi / service crash-loop)."
    warn "Cek log: journalctl -u $SERVICE -f"
fi

banner "SELESAI — langkah berikutnya"
echo "  1) Isi .env :  nano $APP_DIR/.env   (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)"
echo "  2) Restart :  systemctl restart $SERVICE"
echo "  3) Cek    :  systemctl status $SERVICE"
echo "              curl -s http://127.0.0.1:8000/health"
echo "  4) Log    :  journalctl -u $SERVICE -f"
echo "  5) Dokumen lengkap: deploy/README-DEPLOY.md"
