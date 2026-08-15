#!/usr/bin/env python
"""
Cortex — Unified Command Runner for Personal AI Knowledge Base
Usage:
    python cortex <command> [arguments]

Commands:
    serve              Start FastAPI web server & UI (http://127.0.0.1:8000)
    ingest             Ingest file, directory, or URL into knowledge base
    query              Ask questions directly via terminal
    migrate            Run database migrations
    migrate:fresh      Drop all tables and run fresh migrations (--seed to seed)
    migrate:reset      Rollback all database migrations
    db:seed            Run database seeders
    build              Compile frontend SPA (Bun + Vite)
    test               Run full automated test suite
    setup              Initialize environment, database & directories
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _ensure_env():
    env_file = Path(".env")
    example_file = Path(".env.example")
    if not env_file.exists() and example_file.exists():
        print("Creating .env from .env.example...")
        env_file.write_text(example_file.read_text(encoding="utf-8"), encoding="utf-8")


def serve_cmd(args: list[str]):
    from app.Console import ServeCommand
    ServeCommand.run(args)


def ingest_cmd(args: list[str]):
    from app.Console import IngestCommand
    IngestCommand.run(args)


def query_cmd(args: list[str]):
    from app.Console import QueryCommand
    QueryCommand.run(args)


def migrate_cmd(args: list[str]):
    from app.Console import MigrateCommand
    MigrateCommand.run(args, fresh=False, reset=False)


def migrate_fresh_cmd(args: list[str]):
    from app.Console import MigrateCommand
    MigrateCommand.run(args, fresh=True, reset=False)


def migrate_reset_cmd(args: list[str]):
    from app.Console import MigrateCommand
    MigrateCommand.run(args, fresh=False, reset=True)


def seed_cmd(args: list[str]):
    from app.Console import SeedCommand
    SeedCommand.run(args)


def build_cmd(args: list[str]):
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("Frontend directory not found.")
        sys.exit(1)

    print("Building frontend SPA with Bun...")
    cmd = ["bun", "run", "build"]
    try:
        subprocess.run(cmd, cwd=str(frontend_dir), check=True, shell=True)
        print("Frontend build complete! Output in app/static/")
    except Exception as exc:
        print(f"Build failed: {exc}")
        sys.exit(1)


def test_cmd(args: list[str]):
    python_bin = sys.executable
    cmd = [python_bin, "-m", "pytest", "tests/", "--basetemp", ".pytest-tmp", "-q"] + args
    print(f"Running tests: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def setup_cmd(args: list[str]):
    print("Setting up Personal AI Knowledge Base (Cortex)...")
    _ensure_env()

    from app.Console import MigrateCommand
    from app.Core.Config import Settings

    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.staging_dir.mkdir(parents=True, exist_ok=True)
    settings.persist_dir.mkdir(parents=True, exist_ok=True)

    MigrateCommand.run([], fresh=False, seed=True)
    print("Setup complete! Run 'python cortex serve' to start the application.")


COMMANDS = {
    "serve": serve_cmd,
    "start": serve_cmd,
    "ingest": ingest_cmd,
    "query": query_cmd,
    "ask": query_cmd,
    "migrate": migrate_cmd,
    "migrate:fresh": migrate_fresh_cmd,
    "migrate:reset": migrate_reset_cmd,
    "db:seed": seed_cmd,
    "seed": seed_cmd,
    "build": build_cmd,
    "test": test_cmd,
    "setup": setup_cmd,
}


def print_help():
    print("""
Cortex — Personal AI Knowledge Base CLI

Usage:
  python cortex <command> [options]

Available Commands:
  serve [--port 8000]       : Start web server (FastAPI + React 19 UI)
  ingest <path|url>         : Ingest documents (PDF, MD, DOCX, PPTX, HTML, URL)
  query [question]          : Ask questions via terminal
  migrate                   : Run database migrations
  migrate:fresh [--seed]    : Drop all tables, re-run migrations, and optionally seed
  migrate:reset             : Rollback all database migrations
  db:seed                   : Seed initial glossary and flashcard review data
  build                     : Compile frontend SPA with Bun
  test                      : Run automated test suite
  setup                     : Full initialization (.env, migrations, seeders & folders)
""")


def main():
    _ensure_env()

    if len(sys.argv) < 2 or sys.argv[1].lower() in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(f"Unknown command: '{cmd}'")
        print("Available commands: " + ", ".join(COMMANDS.keys()))
        sys.exit(1)

    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
