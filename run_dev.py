"""Launcher 1-perintah untuk RAG Knowledge Base (backend FastAPI saja).

Proyek ini tidak lagi memakai frontend Next.js terpisah — UI statis
dilayani langsung oleh FastAPI di alamat yang sama (http://127.0.0.1:8000).
Launcher ini hanya:
- menjalankan backend FastAPI (uvicorn) dalam satu proses
- memantau kesehatan backend: restart otomatis bila mati, dengan batas
  MAX_FAST_FAILURES agar tidak restart-loop saat port dipakai / error start
- memantau pemakaian RAM pohon proses dan memberi peringatan bila melewati
  ambang (env RAG_BACKEND_RAM_LIMIT_MB, default 2048 MB) — TANPA restart
  otomatis: ChromaDB mengunci file dan model perlu dimuat ulang, jadi
  restart saat RAM tinggi berisiko merusak state
- saat exit, membunuh SELURUH pohon proses (taskkill /T) — mencegah proses
  yatim menumpuk setelah Ctrl+C berulang kali
"""

import os
import signal
import subprocess
import sys
import time

import psutil

# Console Windows (cp1252) gagal encode emoji -> paksa UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

PORT = int(os.getenv("RAG_BACKEND_PORT", "8000"))
BACKEND_RAM_LIMIT_MB = int(os.getenv("RAG_BACKEND_RAM_LIMIT_MB", "2048"))
POLL_INTERVAL_SEC = 5.0
MAX_FAST_FAILURES = 4  # batas restart jika backend mati cepat (< 20 detik)


def _popen(cmd: list[str], cwd: str) -> subprocess.Popen:
    """Buka child dalam grup/sesi proses sendiri supaya bisa di-kill per pohon."""
    kwargs: dict = {"cwd": cwd}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _kill_tree(pid: int) -> None:
    """Bunuh pid + seluruh turunannya (taskkill /T pada Windows)."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
        )
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def _tree_rss_mb(pid: int) -> float:
    """Total RSS (MB) dari pohon proses; 0 bila proses sudah tidak ada."""
    try:
        proc = psutil.Process(pid)
    except psutil.Error:
        return 0.0
    total = proc.memory_info().rss
    for child in proc.children(recursive=True):
        try:
            total += child.memory_info().rss
        except psutil.Error:
            pass
    return total / (1024 * 1024)


def _port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    # Pakai python dari venv proyek; fallback ke interpreter yang sedang
    # menjalankan launcher ini kalau path venv tidak ditemukan.
    python_exe = os.path.join(root, ".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    print("=" * 55)
    print("  🚀 RAG Knowledge Base System")
    print(f"  - UI + API: http://127.0.0.1:{PORT}")
    print("  - UI statis dilayani FastAPI sendiri (tanpa frontend terpisah)")
    print("=" * 55)

    if _port_in_use(PORT):
        print(f"⚠️  Port {PORT} sudah dipakai — proses backend lama masih berjalan?")

    backend_cmd = [
        python_exe,
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(PORT),
    ]

    print("\nStarting FastAPI Backend...")
    p_backend = _popen(backend_cmd, root)
    backend_started_at = time.time()

    stopping = False

    def _stop() -> None:
        nonlocal stopping
        stopping = True

    try:
        signal.signal(signal.SIGINT, lambda *_: _stop())
    except (ValueError, OSError):
        pass
    if os.name != "nt":
        signal.signal(signal.SIGTERM, lambda *_: _stop())

    fast_failures = 0
    ram_warned = False

    try:
        while not stopping:
            time.sleep(POLL_INTERVAL_SEC)

            # Backend mati (crash, error start, port dipakai, dll) -> restart,
            # kecuali gagal cepat berkali-kali berturut-turut.
            if p_backend.poll() is not None:
                elapsed = time.time() - backend_started_at
                if elapsed < 20:
                    fast_failures += 1
                else:
                    fast_failures = 0  # sempat berjalan lama -> hitungan direset
                if fast_failures >= MAX_FAST_FAILURES:
                    print(
                        "\n❌ Backend gagal start berulang kali (mungkin port "
                        f"{PORT} dipakai proses lain atau ada error di awal). "
                        "Berhenti — perbaiki masalahnya lalu jalankan ulang."
                    )
                    break
                print("\n🔄 Backend berhenti, me-restart...")
                p_backend = _popen(backend_cmd, root)
                backend_started_at = time.time()
                continue

            # Pantau RAM pohon backend — cukup peringatan, jangan restart.
            # (ChromaDB mengunci file + model dimuat ulang, restart berisiko.)
            rss = _tree_rss_mb(p_backend.pid)
            if rss > BACKEND_RAM_LIMIT_MB:
                if not ram_warned:
                    print(
                        f"\n⚠️  Pohon proses backend memakai {rss:.0f} MB RAM "
                        f"(batas {BACKEND_RAM_LIMIT_MB} MB). Tidak di-restart "
                        "otomatis — pantau dan restart manual bila perlu."
                    )
                    ram_warned = True
            else:
                ram_warned = False
    finally:
        print("\nStopping server...")
        if p_backend.poll() is None:
            _kill_tree(p_backend.pid)


if __name__ == "__main__":
    main()
