"""Artisan-style Command Kernel for Knowledge Base."""

from __future__ import annotations

import sys
from app.Console import IngestCommand, QueryCommand, ServeCommand

COMMANDS = {
    "ingest": IngestCommand.run,
    "query": QueryCommand.run,
    "ask": QueryCommand.run,
    "serve": ServeCommand.run,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Knowledge Base CLI Runner (Artisan-style)")
        print("\nCommands yang tersedia:")
        print("  ingest <path|url>   : Ingest dokumen atau URL ke VectorStore")
        print("  query [pertanyaan]  : Tanya jawab lewat terminal")
        print("  serve [--port 8000] : Jalankan web server")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(f"❌ Command tidak dikenal: '{cmd}'")
        print("Gunakan salah satu dari: " + ", ".join(COMMANDS.keys()))
        sys.exit(1)

    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
