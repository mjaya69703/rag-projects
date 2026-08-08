"""FastAPI backend: expose logic RAG sebagai REST API + multi-session chat.

Endpoint:
- POST   /upload                     upload & index dokumen (PDF/MD/TXT)
- POST   /ingest-url                 index konten dari URL (fitur #15)
- POST   /query                      tanya jawab (bisa dengan session history)
- GET    /documents                  daftar dokumen terindeks
- DELETE /documents/{source}         hapus dokumen (tercatat di deleted_documents)
- GET    /deleted-documents          daftar dokumen yang pernah dihapus
- GET    /locations?q=               "Where is X covered?" (fitur #8)
- GET    /repeated-questions         termometer pertanyaan berulang (7 hari)
- POST   /sessions/create            buat session chat baru
- GET    /sessions/list              daftar session
- GET    /sessions/{id}/messages     riwayat pesan session
- PUT    /sessions/{id}/rename       rename session
- DELETE /sessions/{id}              hapus session + pesannya
- GET    /learning/due               kartu review yang jatuh tempo (#1)
- POST   /learning/answer            jawab kartu review (Ingat/Lupa) (#1)
- GET    /learning/weak-spots        area lemah (#2)
- GET    /learning/progress          progress bab per dokumen (#3)
- POST   /learning/quiz/generate     buat soal dari materi (#4)
- POST   /learning/quiz/grade        koreksi jawaban quiz (#4)
- GET    /learning/quiz/history      riwayat skor quiz (#4)
- GET    /learning/flashcards        kartu heading (tanpa LLM) (#5)
- GET    /health                     health check
- GET    /metrics                    metrik ringan (cache hit/miss, query, error LLM)

Jalankan: .venv\\Scripts\\uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import annotations, db, learning
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
from app.rag_engine import RAGEngine
from app.url_parser import parse_url
from app.vector_store import VectorStore
from app.watch_folder import SUPPORTED_EXTENSIONS, parse_any, scan_pending

logger = logging.getLogger(__name__)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"

logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)

# Rate limit in-memory: sliding window per IP untuk POST /query,
# /query/stream, dan /upload. Test me-reset lewat _RATE_LIMIT.clear().
_RATE_LIMIT: dict[str, deque] = {}
RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_PATHS = {"/query", "/query/stream", "/upload", "/ingest-url"}

# Watch-folder: interval scan dokumen baru di upload_dir (detik).
WATCH_FOLDER_INTERVAL_SEC = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    db.init_db(settings.db_path)
    learning.ensure_tables(settings.db_path)
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
    # Watch-folder: index otomatis file baru yang di-drop ke upload_dir.
    watch_task = asyncio.create_task(_watch_folder_loop(settings, store))
    app.state.watch_task = watch_task
    try:
        yield
    finally:
        watch_task.cancel()
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
    category: str | None = None
    session_id: str | None = None
    mode: str = Field(default="sliding", pattern="^(sliding|summary)$")
    history_n: int = Field(default=SLIDING_WINDOW_DEFAULT, ge=1, le=50)


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class IngestUrlRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2000)
    source: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)


class SetCategoryRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)


class AnswerCardRequest(BaseModel):
    card_id: str = Field(..., min_length=1)
    remembered: bool


class QuizGenerateRequest(BaseModel):
    source: str | None = None
    n: int = Field(default=5, ge=1, le=20)


class QuizGradeRequest(BaseModel):
    questions: list[dict]
    answers: list[int]


class FlashcardAnswerRequest(BaseModel):
    heading: str = Field(..., min_length=1, max_length=300)
    source: str = Field(..., max_length=300)
    known: bool


from app.watch_folder import SUPPORTED_EXTENSIONS, get_category_for_path, parse_any, scan_pending


def _watch_folder_loop(settings: Settings, store: VectorStore) -> None:
    """Loop asinkron: index otomatis file baru di upload_dir (fitur #6)."""
    import asyncio

    async def loop() -> None:
        while True:
            try:
                await asyncio.sleep(WATCH_FOLDER_INTERVAL_SEC)
                indexed = {d["source"] for d in store.list_documents()}
                pending = scan_pending(settings.upload_dir, indexed)
                for path in pending:
                    source = path.name
                    cat = get_category_for_path(settings.upload_dir, path)
                    chunks = parse_any(path, source=source)
                    if not chunks:
                        continue
                    store.delete_document(source)  # replace
                    store.add_documents(chunks, source=source, category=cat)
                    db.set_document_category(settings.db_path, source, cat)
                    db.clear_deleted_document(settings.db_path, source)
                    logger.info("watch-folder: %s (%s) terindeks (%d chunk)", source, cat, len(chunks))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("watch-folder: error saat scan")

    return loop()


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


@app.get("/repeated-questions")
def repeated_questions(days: int = 7, min_hits: int = 2) -> dict:
    """Termometer read-only: pertanyaan yang diajukan berulang (7 hari).

    Dipakai untuk memvalidasi asumsi "pengguna menanyakan hal yang sama
    berulang" sebelum memutuskan membangun fitur review/spaced repetition.
    Murni agregasi dari tabel messages — tidak ada efek samping.
    """
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "days": days,
        "min_hits": min_hits,
        "usage": db.usage_summary(settings.db_path, days=days),
        "questions": db.repeated_questions(
            settings.db_path, days=days, min_hits=min_hits
        ),
    }


@app.post("/upload")
def upload(
    file: UploadFile = File(...),  # noqa: B008 - idiom FastAPI, bukan default biasa
    source: str | None = Form(default=None),
    category: str | None = Form(default=None),
) -> dict:
    """Upload dokumen (PDF/MD/TXT), parse, chunk, dan index ke ChromaDB."""
    settings: Settings = app.state.settings
    filename = Path(file.filename or "file.pdf").name  # cegah path traversal
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format tidak didukung: {ext}. Gunakan {sorted(SUPPORTED_EXTENSIONS)}.",
        )

    content = file.file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail=f"File maksimal {MAX_UPLOAD_MB} MB."
        )
    if ext == ".pdf" and not content.lstrip().startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid.")

    doc_path = settings.upload_dir / filename
    doc_path.write_bytes(content)

    src = source or filename
    cat = category.strip() if category and category.strip() else "Umum"
    try:
        chunks = parse_any(doc_path, source=src)
    except Exception as exc:
        logger.exception("Gagal memproses dokumen: %s", filename)
        raise HTTPException(
            status_code=400, detail=f"Gagal memproses dokumen: {exc}"
        ) from exc
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada teks yang bisa diekstrak (PDF hasil scan?).",
        )

    store: VectorStore = app.state.store
    removed = store.delete_document(src)  # upload ulang = replace
    db.clear_deleted_document(settings.db_path, src)  # sudah aktif lagi
    n = store.add_documents(chunks, source=src, category=cat)
    db.set_document_category(settings.db_path, src, cat)
    return {
        "status": "ok",
        "source": src,
        "category": cat,
        "kind": ext.lstrip("."),
        "chunks": n,
        "replaced": removed,
        "documents": store.list_documents(),
    }


@app.post("/ingest-url")
def ingest_url(req: IngestUrlRequest) -> dict:
    """Index konten dari URL (fitur #15)."""
    settings: Settings = app.state.settings
    src = req.source or req.url
    cat = req.category.strip() if req.category and req.category.strip() else "Umum"
    try:
        chunks = parse_url(req.url, source=src)
    except Exception as exc:
        logger.exception("Gagal mengambil URL: %s", req.url)
        raise HTTPException(
            status_code=400, detail=f"Gagal mengambil URL: {exc}"
        ) from exc
    if not chunks:
        raise HTTPException(status_code=400, detail="Tidak ada teks yang bisa diekstrak dari URL.")

    store: VectorStore = app.state.store
    removed = store.delete_document(src)  # re-index = replace
    db.clear_deleted_document(settings.db_path, src)
    n = store.add_documents(chunks, source=src, category=cat)
    db.set_document_category(settings.db_path, src, cat)
    return {
        "status": "ok",
        "source": src,
        "category": cat,
        "kind": "url",
        "chunks": n,
        "replaced": removed,
        "documents": store.list_documents(),
    }


@app.post("/query")
def query(req: QueryRequest) -> dict:
    """Tanya jawab berdasarkan dokumen terindeks (+ konteks session bila ada)."""
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    where: dict | None = {}
    if req.source:
        where["source"] = req.source
    if req.category:
        where["category"] = req.category
    if not where:
        where = None

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

    # Grounding: filter ke dokumen yang tidak (lagi) ada di indeks.
    if req.source:
        status = engine.document_status(req.source, settings.db_path)
        if not status["exists"]:
            hint = "sudah dihapus dari indeks" if status["deleted"] else "belum pernah diindeks"
            detail = (
                f"Dokumen '{req.source}' {hint}. Dokumen yang aktif: "
                f"{', '.join(status['available']) or 'tidak ada'}."
            )
            if session_info is not None:
                db.add_message(settings.db_path, req.session_id, "user", req.question, [])
                db.add_message(settings.db_path, req.session_id, "assistant", detail, [])
            return {
                "status": "ok",
                "answer": detail,
                "cached": False,
                "model": None,
                "sources": [],
                "grounded": False,
                "document_missing": True,
                "session": session_info,
            }

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
        "grounded": answer.grounded,
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
    where: dict | None = {}
    if req.source:
        where["source"] = req.source
    if req.category:
        where["category"] = req.category
    if not where:
        where = None

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

    # Grounding: filter ke dokumen yang tidak (lagi) ada di indeks.
    if req.source:
        status = engine.document_status(req.source, settings.db_path)
        if not status["exists"]:
            hint = "sudah dihapus dari indeks" if status["deleted"] else "belum pernah diindeks"
            detail = (
                f"Dokumen '{req.source}' {hint}. Dokumen yang aktif: "
                f"{', '.join(status['available']) or 'tidak ada'}."
            )
            if session_info is not None:
                db.add_message(settings.db_path, req.session_id, "user", req.question, [])
                db.add_message(settings.db_path, req.session_id, "assistant", detail, [])
                session_info = _post_query_tasks(
                    engine, settings.db_path, req.session_id, req.question
                )

            async def missing_gen():
                yield _sse(
                    {
                        "type": "meta",
                        "sources": [],
                        "cached": False,
                        "model": None,
                        "grounded": False,
                        "document_missing": True,
                    }
                )
                yield _sse({"type": "delta", "text": detail})
                yield _sse({"type": "done", "answer": detail, "session": session_info})

            return StreamingResponse(missing_gen(), media_type="text/event-stream")

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
                    grounded = ev.get("grounded", True)
                    sources_json = [_s_dict(s) for s in ev["sources"]]
                    _record_query(metrics, cached)
                    yield _sse(
                        {
                            "type": "meta",
                            "cached": cached,
                            "model": model,
                            "grounded": grounded,
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
        "chunk_index": s.chunk_index,
    }


# ----------------------------------------------------------------------
# Annotations (fitur #9) — catatan pribadi pada chunk
# ----------------------------------------------------------------------
class AnnotationRequest(BaseModel):
    note: str = Field(..., max_length=2000)


@app.get("/annotations")
def list_annotations() -> dict:
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "annotations": annotations.list_annotations(settings.db_path),
    }


@app.put("/annotations/{chunk_key}")
def upsert_annotation(chunk_key: str, req: AnnotationRequest) -> dict:
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "annotation": annotations.upsert_note(
            settings.db_path, chunk_key, req.note
        ),
    }


@app.delete("/annotations/{chunk_key}")
def delete_annotation(chunk_key: str) -> dict:
    settings: Settings = app.state.settings
    annotations.upsert_note(settings.db_path, chunk_key, "")
    return {"status": "ok", "chunk_key": chunk_key}


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
    settings: Settings = app.state.settings
    cats = db.list_document_categories(settings.db_path)
    docs = store.list_documents()
    for d in docs:
        d["category"] = cats.get(d["source"], "Umum")
    return {"status": "ok", "documents": docs}


@app.get("/categories")
def list_categories() -> dict:
    settings: Settings = app.state.settings
    return {"status": "ok", "categories": db.list_all_categories(settings.db_path)}


@app.put("/documents/{source}/category")
def set_document_category(source: str, req: SetCategoryRequest) -> dict:
    settings: Settings = app.state.settings
    store: VectorStore = app.state.store
    cat = req.category.strip() or "Umum"
    db.set_document_category(settings.db_path, source, cat)
    store.update_document_category(source, cat)
    return {"status": "ok", "source": source, "category": cat}


@app.get("/deleted-documents")
def deleted_documents() -> dict:
    """Daftar dokumen yang pernah dihapus (grounding: 'sudah dihapus')."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "documents": db.list_deleted_documents(settings.db_path),
    }


@app.get("/locations")
def locations(q: str = "", top_k: int = 15) -> dict:
    """"Where is X covered?" (fitur #8): peta lokasi topik di dokumen."""
    engine: RAGEngine = app.state.engine
    if not q.strip():
        return {"status": "ok", "locations": []}
    return {
        "status": "ok",
        "locations": engine.find_locations(q, top_k=top_k),
    }


@app.delete("/documents/{source}")
def delete_document(source: str) -> dict:
    store: VectorStore = app.state.store
    settings: Settings = app.state.settings
    removed = store.delete_document(source)
    if removed == 0:
        raise HTTPException(
            status_code=404, detail=f"Dokumen '{source}' tidak ditemukan."
        )
    db.record_deleted_document(settings.db_path, source)
    return {"status": "ok", "source": source, "removed": removed}


# ----------------------------------------------------------------------
# Learning loop (fitur #1-#5) — review mode, weak-spot, progress, quiz, flashcards
# ----------------------------------------------------------------------
@app.get("/learning/due")
def learning_due(limit: int = 10) -> dict:
    """Kartu review yang jatuh tempo (fitur #1)."""
    settings: Settings = app.state.settings
    learning.sync_cards(settings.db_path)
    return {
        "status": "ok",
        "cards": learning.due_cards(settings.db_path, limit=limit),
        "stats": learning.card_stats(settings.db_path),
    }


@app.post("/learning/answer")
def learning_answer(req: AnswerCardRequest) -> dict:
    """Catat jawaban kartu review: remembered=True naikkan interval (#1)."""
    settings: Settings = app.state.settings
    try:
        card = learning.answer_card(
            settings.db_path, req.card_id, req.remembered
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {"status": "ok", "card": card}


@app.get("/learning/weak-spots")
def learning_weak_spots(limit: int = 8) -> dict:
    """Topik yang paling sering diulang / sering lupa (#2)."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "weak_spots": learning.weak_spots(settings.db_path, limit=limit),
    }


@app.get("/learning/progress")
def learning_progress() -> dict:
    """Bab per dokumen yang sudah/belum dibahas (#3)."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "documents": learning.document_progress(settings.db_path),
    }


@app.post("/learning/quiz/generate")
def learning_quiz_generate(req: QuizGenerateRequest) -> dict:
    """Buat soal pilihan ganda dari materi (#4)."""
    engine: RAGEngine = app.state.engine
    try:
        questions = learning.generate_quiz(engine, source=req.source, n=req.n)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return {"status": "ok", "questions": questions}


@app.post("/learning/quiz/grade")
def learning_quiz_grade(req: QuizGradeRequest) -> dict:
    """Koreksi jawaban quiz via LLM (#4)."""
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    try:
        result = learning.grade_quiz(engine, req.questions, req.answers)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    source = req.questions[0].get("source") if req.questions else ""
    learning.save_quiz_score(settings.db_path, source, result["score"], result["total"])
    return {"status": "ok", **result}


@app.get("/learning/quiz/history")
def learning_quiz_history(limit: int = 20) -> dict:
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "history": learning.quiz_history(settings.db_path, limit=limit),
    }


@app.get("/learning/flashcards")
def learning_flashcards(source: str | None = None, limit: int = 20) -> dict:
    """Kartu Q&A dari heading dokumen, tanpa LLM (#5)."""
    store: VectorStore = app.state.store
    return {
        "status": "ok",
        "cards": learning.flashcards(store, source=source, limit=limit),
    }


@app.post("/learning/flashcards/answer")
def learning_flashcards_answer(req: FlashcardAnswerRequest) -> dict:
    """Catat tahu/belum sebuah kartu flashcard."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "card": learning.answer_flashcard(
            settings.db_path, req.heading, req.source, req.known
        ),
    }


@app.get("/learning/flashcards/stats")
def learning_flashcards_stats(limit: int = 50) -> dict:
    """Statistik kartu: tahu vs belum, urut paling sering salah."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "stats": learning.flashcard_stats(settings.db_path, limit=limit),
    }


@app.get("/documents/{source}/chunks")
def document_chunks(source: str, limit: int = 100) -> dict:
    """Isi satu dokumen: daftar chunk (halaman + heading + teks) (Library).

    Dipakai untuk preview/annotasi chunk dari halaman Library.
    """
    store: VectorStore = app.state.store
    result = store.collection.get(
        where={"source": source}, limit=limit, include=["documents", "metadatas"]
    )
    docs = result.get("documents") or []
    metas = result.get("metadatas") or []
    chunks = [
        {
            "chunk_index": (m or {}).get("chunk_index", i),
            "page": (m or {}).get("page", 0),
            "heading": (m or {}).get("heading", ""),
            "text": d,
        }
        for i, (d, m) in enumerate(zip(docs, metas, strict=True))
    ]
    chunks.sort(key=lambda c: c["chunk_index"])
    return {"status": "ok", "source": source, "chunks": chunks}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    """SPA fallback (React): serve file statis kalau ada, selain itu
    index.html — React Router yang menentukan halaman (/library, /quiz, …).
    Route API di atas tetap diprioritaskan karena terdaftar lebih dulu.
    """
    candidate = FRONTEND_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(FRONTEND_DIR / "index.html")
