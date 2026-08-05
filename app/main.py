"""FastAPI backend: expose logic RAG sebagai REST API + multi-session chat.

Endpoint:
- POST   /upload                     upload & index PDF
- POST   /query                      tanya jawab (bisa dengan session history)
- GET    /documents                  daftar dokumen terindeks
- DELETE /documents/{source}         hapus dokumen
- POST   /sessions/create            buat session chat baru
- GET    /sessions/list              daftar session
- GET    /sessions/{id}/messages     riwayat pesan session
- PUT    /sessions/{id}/rename       rename session
- DELETE /sessions/{id}              hapus session + pesannya
- GET    /health                     health check
- GET    /metrics                    metrik ringan (cache hit/miss, query, error LLM)

Jalankan: .venv\\Scripts\\uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.config import (
    CORS_ORIGINS,
    MAX_UPLOAD_MB,
    SLIDING_WINDOW_DEFAULT,
    SUMMARY_INTERVAL,
    SUMMARY_RECENT,
    TOKEN_WARNING,
    Settings,
)
from app.llm_client import LLMError
from app.pdf_parser import parse_pdf
from app.rag_engine import RAGEngine
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"

logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)

# Rate limit in-memory: sliding window per IP untuk POST /query,
# /query/stream, dan /upload. Test me-reset lewat _RATE_LIMIT.clear().
_RATE_LIMIT: dict[str, deque] = {}
RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_PATHS = {"/query", "/query/stream", "/upload"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    db.init_db(settings.db_path)
    store = VectorStore(persist_dir=settings.persist_dir)
    engine = RAGEngine(store=store)
    app.state.settings = settings
    app.state.store = store
    app.state.engine = engine
    app.state.metrics = {
        "cache_hits": 0,
        "cache_misses": 0,
        "queries": 0,
        "llm_errors": 0,
    }
    _setup_file_logging(settings.log_dir)
    logger.info(
        "API siap: persist=%s upload=%s db=%s dokumen=%d session=%d",
        settings.persist_dir,
        settings.upload_dir,
        settings.db_path,
        store.count(),
        len(db.list_sessions(settings.db_path)),
    )
    yield
    store.close()


app = FastAPI(
    title="Personal AI Knowledge Base",
    version="0.2.0",
    description="RAG API: upload PDF, tanya jawab dengan sumber, multi-session chat.",
    lifespan=lifespan,
)

# CORS: origin eksplisit dengan allow_credentials=True. Bila CORS_ORIGINS="*",
# credentials harus False (aturan browser), jadi cukup echo "*".
_cors_star = CORS_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_star else CORS_ORIGINS,
    allow_credentials=not _cors_star,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Frontend custom tanpa runtime terpisah: FastAPI menyajikan SPA statis setelah
# seluruh route API didaftarkan (mount berada di bagian paling bawah file).
FRONTEND_DIR = Path(__file__).resolve().parent / "static"


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    source: str | None = None
    session_id: str | None = None
    mode: str = Field(default="sliding", pattern="^(sliding|summary)$")
    history_n: int = Field(default=SLIDING_WINDOW_DEFAULT, ge=1, le=50)


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


def _setup_file_logging(log_dir: str) -> None:
    """Pasang RotatingFileHandler (5MB x 3) ke root logger bila LOG_DIR diisi."""
    if not log_dir:
        return
    root = logging.getLogger()
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return  # sudah terpasang (lifespan bisa berjalan berulang di test)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)


def _record_query(metrics: dict, cached: bool) -> None:
    """Catat metrik query + status cache (hit/miss)."""
    metrics["queries"] += 1
    if cached:
        metrics["cache_hits"] += 1
    else:
        metrics["cache_misses"] += 1


def _rate_limit_allow(ip: str, qpm: int) -> bool:
    """True jika request masih dalam batas qpm (sliding window 60 detik)."""
    if qpm <= 0:
        return True
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    stamps = _RATE_LIMIT.setdefault(ip, deque())
    while stamps and stamps[0] <= cutoff:
        stamps.popleft()
    if len(stamps) >= qpm:
        return False
    stamps.append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Batasi POST /query, /query/stream, /upload per IP (RATE_LIMIT_QPM)."""
    if request.method == "POST" and request.url.path in RATE_LIMIT_PATHS:
        settings = getattr(request.app.state, "settings", None)
        qpm = getattr(settings, "rate_limit_qpm", 0) if settings is not None else 0
        ip = request.client.host if request.client else "unknown"
        if not _rate_limit_allow(ip, qpm):
            return JSONResponse(
                status_code=429,
                content={"detail": "Terlalu banyak permintaan. Coba lagi sebentar lagi."},
            )
    return await call_next(request)


@app.middleware("http")
async def log_requests(request, call_next):
    """Logging terstruktur: request id, method, path, status, durasi."""
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Jaring error tak terduga jadi 500 JSON (HTTPException/422 tetap normal)."""
    logger.exception("Error tak terduga pada %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "Terjadi kesalahan internal."}
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Metrik ringan tanpa dependency: cache hit/miss, query, error LLM."""
    return dict(getattr(app.state, "metrics", {}))


@app.post("/upload")
def upload(
    file: UploadFile = File(...),  # noqa: B008 - idiom FastAPI, bukan default biasa
    source: str | None = Form(default=None),
) -> dict:
    """Upload PDF, parse, chunk, dan index ke ChromaDB."""
    settings: Settings = app.state.settings
    filename = Path(file.filename or "file.pdf").name  # cegah path traversal
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    content = file.file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail=f"File maksimal {MAX_UPLOAD_MB} MB."
        )
    if not content.lstrip().startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid.")

    pdf_path = settings.upload_dir / filename
    pdf_path.write_bytes(content)

    src = source or filename
    try:
        chunks = parse_pdf(pdf_path, source=src)
    except Exception as exc:
        logger.exception("Gagal memproses PDF: %s", filename)
        raise HTTPException(
            status_code=400, detail=f"Gagal memproses PDF: {exc}"
        ) from exc
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada teks yang bisa diekstrak (PDF hasil scan?).",
        )

    store: VectorStore = app.state.store
    removed = store.delete_document(src)  # upload ulang = replace
    n = store.add_documents(chunks, source=src)
    return {
        "status": "ok",
        "source": src,
        "chunks": n,
        "replaced": removed,
        "documents": store.list_documents(),
    }


@app.post("/query")
def query(req: QueryRequest) -> dict:
    """Tanya jawab berdasarkan dokumen terindeks (+ konteks session bila ada)."""
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    where = {"source": req.source} if req.source else None

    history: list[dict] = []
    session_info: dict | None = None
    summary: str | None = None
    if req.session_id:
        session = db.get_session(settings.db_path, req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
        history, session_info, summary = _build_history(
            settings.db_path, req.session_id, req.mode, req.history_n
        )

    # Simpan pertanyaan user SEBELUM call LLM (auto-title butuh pesan pertama)
    if session_info is not None:
        db.add_message(settings.db_path, req.session_id, "user", req.question, [])

    try:
        answer = engine.query(
            req.question,
            top_k=req.top_k,
            where=where,
            history=history,
            summary=summary,
        )
    except LLMError as exc:
        app.state.metrics["llm_errors"] += 1
        # from None: detail error internal tidak perlu dirantai ke traceback
        raise HTTPException(status_code=502, detail=str(exc)) from None
    _record_query(app.state.metrics, answer.cached)

    # Simpan jawaban + update session
    if session_info is not None:
        db.add_message(
            settings.db_path,
            req.session_id,
            "assistant",
            answer.answer,
            [_s_dict(s) for s in answer.sources],
        )
        session_info = _post_query_tasks(
            engine, settings.db_path, req.session_id, req.question
        )

    return {
        "status": "ok",
        "answer": answer.answer,
        "cached": answer.cached,
        "model": answer.model,
        "sources": [_s_dict(s) for s in answer.sources],
        "session": session_info,
    }


@app.post("/query/stream")
async def query_stream(req: QueryRequest) -> StreamingResponse:
    """Versi streaming (SSE) dari /query — jawaban mengalir per-token.

    Event: {"type": "meta", ...} -> {"type": "delta", "text"} x N ->
           {"type": "done", "answer", "session"} | {"type": "error", "detail"}
    """
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    where = {"source": req.source} if req.source else None

    history: list[dict] = []
    session_info: dict | None = None
    summary: str | None = None
    if req.session_id:
        session = db.get_session(settings.db_path, req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
        history, session_info, summary = _build_history(
            settings.db_path, req.session_id, req.mode, req.history_n
        )

    if session_info is not None:
        db.add_message(settings.db_path, req.session_id, "user", req.question, [])

    metrics = app.state.metrics

    async def event_gen():
        full_answer = ""
        sources_json: list[dict] = []
        cached = False
        model = None
        try:
            async for ev in engine.stream_query(
                req.question,
                top_k=req.top_k,
                where=where,
                history=history,
                summary=summary,
            ):
                if ev["type"] == "meta":
                    cached = ev["cached"]
                    model = ev["model"]
                    sources_json = [_s_dict(s) for s in ev["sources"]]
                    _record_query(metrics, cached)
                    yield _sse(
                        {
                            "type": "meta",
                            "cached": cached,
                            "model": model,
                            "sources": sources_json,
                        }
                    )
                elif ev["type"] == "delta":
                    full_answer += ev["text"]
                    yield _sse({"type": "delta", "text": ev["text"]})
                elif ev["type"] == "done":
                    full_answer = ev["answer"] or full_answer
            # Finalisasi session setelah jawaban lengkap
            final_session = session_info
            if session_info is not None:
                db.add_message(
                    settings.db_path,
                    req.session_id,
                    "assistant",
                    full_answer,
                    sources_json,
                )
                final_session = _post_query_tasks(
                    engine, settings.db_path, req.session_id, req.question
                )
            yield _sse(
                {
                    "type": "done",
                    "answer": full_answer,
                    "cached": cached,
                    "model": model,
                    "session": final_session,
                }
            )
        except LLMError as exc:
            metrics["llm_errors"] += 1
            yield _sse({"type": "error", "detail": str(exc)})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _build_history(
    db_path: str, session_id: str, mode: str, history_n: int
) -> tuple[list[dict], dict, str | None]:
    """Susun riwayat sesuai strategi konteks: sliding window atau summary.

    Return: (history, session_info, summary_text)
    - summary_text diisi jika ada ringkasan percakapan lama yang perlu
      disuntikkan sebagai memori jangka panjang (anti-pelupa).
    """
    summary_text: str | None = None
    if mode == "summary":
        summary = db.get_summary(db_path, session_id)
        recent = db.get_messages(db_path, session_id, limit=SUMMARY_RECENT)
        history: list[dict] = []
        if summary:
            summary_text = summary["summary_text"]
        history.extend({"role": m["role"], "content": m["content"]} for m in recent)
    else:  # sliding window + memori jangka panjang
        count = db.message_count(db_path, session_id)
        tokens = db.estimate_tokens(db_path, session_id)
        summary = db.get_summary(db_path, session_id)

        # Kalau sudah melewati ambang token, kurangi jendela agar tetap muat
        effective_n = history_n
        if tokens > TOKEN_WARNING:
            effective_n = min(history_n, 10)
        recent = db.get_messages(db_path, session_id, limit=effective_n)
        history = [{"role": m["role"], "content": m["content"]} for m in recent]

        # Percakapan panjang (> jendela) + ada ringkasan -> sertakan ringkasan
        # sebagai memori jangka panjang supaya LLM tidak lupa konteks awal.
        if summary and count > effective_n:
            summary_text = summary["summary_text"]

    count = db.message_count(db_path, session_id)
    tokens = db.estimate_tokens(db_path, session_id)
    session = db.get_session(db_path, session_id)
    session_info = {
        "id": session["id"],
        "title": session["title"],
        "messages": count,
        "tokens_est": tokens,
        "over_token_warning": tokens > TOKEN_WARNING,
        "mode": mode,
    }
    return history, session_info, summary_text


def _post_query_tasks(
    engine: RAGEngine, db_path: str, session_id: str, first_question: str
) -> dict:
    """Auto-title (pesan pertama) & auto-summary (tiap 10 pesan)."""
    session = db.get_session(db_path, session_id)
    count = db.message_count(db_path, session_id)

    if session["title"] == "New Chat":
        title = engine.generate_title(first_question)
        db.rename_session(db_path, session_id, title)

    if count >= SUMMARY_INTERVAL and count % SUMMARY_INTERVAL == 0:
        summary = db.get_summary(db_path, session_id)
        if summary is None or summary["last_message_index"] < count:
            messages = db.get_messages(db_path, session_id)
            text = engine.summarize(messages)
            if text:
                db.save_summary(db_path, session_id, text, count)

    return _build_history(db_path, session_id, "sliding", SLIDING_WINDOW_DEFAULT)[1]


def _s_dict(s) -> dict:
    return {
        "source": s.source,
        "page": s.page,
        "heading": s.heading,
        "text": s.text,
        "distance": s.distance,
    }


# ----------------------------------------------------------------------
# Sessions
# ----------------------------------------------------------------------
@app.post("/sessions/create")
def create_session() -> dict:
    settings: Settings = app.state.settings
    return {"status": "ok", "session": db.create_session(settings.db_path)}


@app.get("/sessions/list")
def list_sessions() -> dict:
    settings: Settings = app.state.settings
    return {"status": "ok", "sessions": db.list_sessions(settings.db_path)}


@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str) -> dict:
    settings: Settings = app.state.settings
    if db.get_session(settings.db_path, session_id) is None:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
    return {
        "status": "ok",
        "messages": db.get_messages(settings.db_path, session_id),
    }


@app.put("/sessions/{session_id}/rename")
def rename_session(session_id: str, req: RenameRequest) -> dict:
    settings: Settings = app.state.settings
    if not db.rename_session(settings.db_path, session_id, req.title):
        raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
    return {"status": "ok", "session": db.get_session(settings.db_path, session_id)}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    settings: Settings = app.state.settings
    if not db.delete_session(settings.db_path, session_id):
        raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
    return {"status": "ok", "session_id": session_id}


@app.get("/documents")
def documents() -> dict:
    store: VectorStore = app.state.store
    return {"status": "ok", "documents": store.list_documents()}


@app.delete("/documents/{source}")
def delete_document(source: str) -> dict:
    store: VectorStore = app.state.store
    removed = store.delete_document(source)
    if removed == 0:
        raise HTTPException(
            status_code=404, detail=f"Dokumen '{source}' tidak ditemukan."
        )
    return {"status": "ok", "source": source, "removed": removed}


# Harus diletakkan terakhir: StaticFiles pada "/" adalah fallback untuk UI,
# sedangkan endpoint API di atas tetap diprioritaskan oleh router.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="web")
