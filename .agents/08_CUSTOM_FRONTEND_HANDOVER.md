# Custom Frontend Handover

Updated 2026-08-03.

The Streamlit frontend has been replaced by a custom static web application.
FastAPI serves `app/static/index.html` from `/`; keep `app.mount("/", StaticFiles(...))`
at the bottom of `app/main.py` so API routes retain priority.

Frontend files:

- `app/static/index.html`: semantic shell, dialogs, and accessible controls.
- `app/static/tokens.css`: shared OKLCH design tokens and dark-theme overrides.
- `app/static/styles.css`: responsive workspace layout.
- `app/static/app.js`: session/document management and SSE client for `/query/stream`.

No Node build or extra frontend server is required. Run one process:

```cmd
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Open `http://127.0.0.1:8000`. The key smoke test is
`.venv\Scripts\python -m pytest tests\test_frontend.py -q`.

The interface depends on the existing API contracts: sessions CRUD, documents CRUD,
`/upload`, and SSE `/query/stream`. Preserve those response shapes when changing the
backend. The command palette is `Ctrl/Cmd+K`; it provides new-chat, upload, and theme
actions. The SPA automatically creates a first session only after `/health` succeeds.
