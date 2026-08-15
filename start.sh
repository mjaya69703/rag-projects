#!/usr/bin/env bash
set -e

echo "==================================================="
echo "  Personal AI Knowledge Base (Cortex Engine)"
echo "  http://127.0.0.1:8000"
echo "==================================================="

if [ ! -d ".venv" ]; then
    echo "[Membuat virtual environment .venv...]"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

python cortex serve
