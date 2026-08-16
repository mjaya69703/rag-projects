"""CLI command for running the FastAPI application."""

from __future__ import annotations

import argparse

import uvicorn


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Start Knowledge Base Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    opts = parser.parse_args(args)

    print(f"🚀 Menjalankan Knowledge Base di http://{opts.host}:{opts.port}")
    uvicorn.run("app.main:app", host=opts.host, port=opts.port, reload=opts.reload)
