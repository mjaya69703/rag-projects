@echo off
setlocal
echo ===================================================
echo   Personal AI Knowledge Base (Cortex Engine)
echo   http://127.0.0.1:8000
echo ===================================================

if not exist .venv (
    echo [.venv tidak ditemukan, membuat virtual environment...]
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

python cortex serve
