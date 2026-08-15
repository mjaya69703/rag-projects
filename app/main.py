"""FastAPI backend: expose logic RAG sebagai REST API + multi-session chat.

Keamanan (P0-02): isi env API_TOKEN untuk mengunci semua endpoint API
(kecuali /health & SPA statis) dengan `Authorization: Bearer <token>`
(fail-closed); aksi terproteksi tercatat di audit log (GET /audit).

Endpoint:
- POST   /upload                      upload -> job ingestion asinkron (poll GET /jobs/{id})
- POST   /ingest-url                  index URL -> job ingestion asinkron
- GET    /jobs, /jobs/{job_id}        status job ingestion
- POST   /query                       tanya jawab (bisa dengan session history)
- POST   /query/stream                versi SSE dari /query
- GET    /documents                   daftar dokumen terindeks
- DELETE /documents/{source}          hapus index (?purge=true = hapus file fisik)
- GET    /deleted-documents           daftar dokumen yang pernah dihapus
- GET    /locations?q=                "Where is X covered?" (fitur #8)
- GET    /repeated-questions          termometer pertanyaan berulang (7 hari)
- POST   /sessions/create             buat session chat baru
- GET    /sessions/list               daftar session
- GET    /sessions/{id}/messages      riwayat pesan session
- PUT    /sessions/{id}/rename        rename session
- DELETE /sessions/{id}               hapus session + pesannya
- GET    /learning/due                kartu review yang jatuh tempo (#1)
- POST   /learning/answer             jawab kartu review (scheduler SM-2, #1)
- GET    /learning/weak-spots         area lemah + mastery stats (#2)
- GET    /learning/progress           progress bab per dokumen (#3)
- POST   /learning/quiz/generate      terbitkan paket kuis (attempt_id, #4)
- POST   /learning/quiz/grade         koreksi deterministik dari kunci server (#4)
- GET    /learning/quiz/history       riwayat skor quiz (#4)
- GET    /learning/flashcards         kartu heading (tanpa LLM) (#5)
- GET    /privacy/info                disclosure data flow + retensi (P0-03)
- DELETE /privacy/data, /privacy/cache  hapus data pribadi / cache (P0-03)
- GET    /health                      health check publik (systemd)
- GET    /metrics                     metrik operasional (latensi, disk, ingestion)

Jalankan: .venv\\Scripts\\uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import logging.handlers
import sqlite3
import shutil
import statistics
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from starlette.routing import Match

from app import annotations, db, glossary, learning
from app.config import (
    CORS_ORIGINS,
    MAX_UPLOAD_MB,
    PUBLIC_API_PATHS,
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
from app.watch_folder import SUPPORTED_EXTENSIONS, get_category_for_path, parse_any, scan_pending

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

# Serialisasi job ingestion (upload/URL) vs watch-folder vs update kategori.
# Aplikasi ini single-process (uvicorn workers=1); lock ini melengkapi
# lock mutasi di VectorStore (P1-06: kebijakan concurrency eksplisit).
_INGEST_LOCK = threading.Lock()

# Route API yang terproteksi auth (P0-02), dihitung lazy dari app.routes.
_protected_routes: list | None = None


def _get_protected_routes() -> list:
    """Semua route API (APIRoute) kecuali jalur publik (mis. /health)
    dan catch-all SPA (/{full_path:path}) yang melayani file statis."""
    global _protected_routes
    if _protected_routes is None:
        _protected_routes = [
            r
            for r in app.routes
            if isinstance(r, APIRoute)
            and r.path not in PUBLIC_API_PATHS
            and r.path != "/{full_path:path}"  # SPA fallback, publik
        ]
    return _protected_routes


def _is_protected_api(scope: dict) -> bool:
    """True jika request mengenai route API yang butuh autentikasi.

    SPA statis (spa_fallback, path tanpa route API) tidak ikut diblokir.
    """
    for route in _get_protected_routes():
        if route.matches(scope)[0] is Match.FULL:
            return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.staging_dir.mkdir(parents=True, exist_ok=True)
    db.init_db(settings.db_path)
    learning.ensure_tables(settings.db_path)
    store = VectorStore(persist_dir=settings.persist_dir)
    engine = RAGEngine(store=store)
    app.state.settings = settings
    app.state.store = store
    app.state.engine = engine
    app.state.started_at = time.time()
    app.state.metrics = {
        "cache_hits": 0,
        "cache_misses": 0,
        "queries": 0,
        "llm_errors": 0,
        "requests": 0,
        "latency_ms": deque(maxlen=500),  # rolling window untuk p50/p95
        "ingestion": {"total": 0, "failed": 0, "pending": 0, "ready": 0},
    }
    _setup_file_logging(settings.log_dir)

    # Retensi data pribadi (P0-03): purge chat lama & cache semantic TTL.
    if settings.retain_chat_days > 0:
        purged = db.purge_old_chats(settings.db_path, settings.retain_chat_days)
        if purged:
            logger.info(
                "retensi: %d session tidak diakses >= %d hari dihapus",
                purged, settings.retain_chat_days,
            )
    if settings.cache_max_days > 0:
        try:
            from app.semantic_cache import SemanticCache

            n = SemanticCache(store).purge_older_than(settings.cache_max_days)
            if n:
                logger.info("retensi: %d entri cache semantic dihapus", n)
        except Exception:
            logger.exception("retensi: gagal purge semantic cache")

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
    remembered: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=4)


class FlashcardGenerateRequest(BaseModel):
    source: str | None = None
    n: int = Field(default=5, ge=1, le=25)
    save_to_deck: bool = True


class CustomCardRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    answer: str = Field(..., min_length=1, max_length=5000)
    source: str | None = None


class QuizGenerateRequest(BaseModel):
    source: str | None = None
    n: int = Field(default=5, ge=1, le=20)


class QuizGradeRequest(BaseModel):
    attempt_id: str = Field(..., min_length=1, max_length=64)
    answers: list[int]


class FlashcardAnswerRequest(BaseModel):
    heading: str = Field(..., min_length=1, max_length=300)
    source: str = Field(..., max_length=300)
    known: bool


def _index_chunks(
    settings: Settings,
    store: VectorStore,
    source: str,
    category: str,
    chunks,
    job_id: str = "",
) -> int:
    """Seragamkan update index + metadata + registry untuk satu dokumen.

    Dipakai upload job, ingest-url job, dan watch-folder supaya lifecycle
    file/index/metadata konsisten (P1-02).
    """
    with _INGEST_LOCK:
        n = store.replace_document(chunks, source=source, category=category)
        db.set_document_category(settings.db_path, source, category)
        db.clear_deleted_document(settings.db_path, source)
        db.update_document_status(
            settings.db_path, source, "ready",
            chunks=n, category=category, job_id=job_id,
        )
        return n


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _safe_unlink(path: Path, attempts: int = 3) -> None:
    """Hapus file dengan retry — parser (mis. PyMuPDF) kadang masih
    memegang handle pada Windows sampai GC. Jangan pernah crash karena ini."""
    import gc

    for i in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if i == attempts - 1:
                logger.warning("gagal hapus file sementara: %s", path)
                return
            gc.collect()
            time.sleep(0.2)


def _ingest_file_job(
    settings: Settings,
    store: VectorStore,
    staged: Path,
    source: str,
    category: str,
    kind: str,
    job_id: str,
    checksum: str,
) -> None:
    """Job background (threadpool): parse staging -> index -> pindah final.

    Status registry: queued -> processing -> ready | error. File staging
    dibersihkan di kedua ujung; file hanya dipindah ke upload_dir setelah
    parsing sukses (P1-01: tidak ada file invalid yang tertinggal).
    """
    metrics = app.state.metrics["ingestion"]
    metrics["pending"] += 1
    db.update_document_status(settings.db_path, source, "processing", job_id=job_id)
    try:
        existing = db.get_document(settings.db_path, source)
        # Dedup: versi ready dengan checksum sama -> tidak perlu re-embed.
        if (
            existing
            and existing.get("status") == "ready"
            and existing.get("checksum") == checksum
        ):
            staged.unlink(missing_ok=True)
            db.update_document_status(settings.db_path, source, "ready", job_id=job_id)
            logger.info("ingest: %s tidak berubah (checksum sama), dilewati", source)
            metrics["ready"] += 1
            return

        chunks = parse_any(staged, source=source)
        if not chunks:
            raise ValueError("Tidak ada teks yang bisa diekstrak (PDF hasil scan?).")

        # Gunakan nama file asli bersih tanpa prefix uuid staging
        clean_filename = Path(source).name if source else Path(staged.name).name
        if len(clean_filename) > 33 and clean_filename[32] == "_" and all(c in "0123456789abcdefABCDEF" for c in clean_filename[:32]):
            clean_filename = clean_filename[33:]
        final_path = settings.upload_dir / clean_filename

        if staged.exists():
            if final_path.exists() and str(staged.resolve()) != str(final_path.resolve()):
                _safe_unlink(final_path)
            shutil.move(str(staged), str(final_path))

        n = _index_chunks(settings, store, source, category, chunks, job_id=job_id)
        db.update_document_status(
            settings.db_path, source, "ready",
            chunks=n, file_path=str(final_path), checksum=checksum,
            category=category, job_id=job_id,
        )
        metrics["total"] += 1
        metrics["ready"] += 1
        logger.info("ingest: %s (%s) terindeks (%d chunk)", source, kind, n)
    except Exception as exc:
        logger.exception("ingest gagal: %s", source)
        db.update_document_status(
            settings.db_path, source, "error",
            error=str(exc)[:500], job_id=job_id,
        )
        # Bebaskan referensi exception: traceback-nya memegang frame locals
        # parser (mis. objek PyMuPDF yang masih membuka file) sehingga handle
        # file bisa dilepas GC — wajib di Windows sebelum unlink staging.
        del exc
        _safe_unlink(staged)
        metrics["failed"] += 1
    finally:
        metrics["pending"] -= 1


def _ingest_url_job(
    settings: Settings,
    store: VectorStore,
    url: str,
    source: str,
    category: str,
    job_id: str,
) -> None:
    """Job background untuk ingest URL (parse jaringan di threadpool)."""
    metrics = app.state.metrics["ingestion"]
    metrics["pending"] += 1
    db.update_document_status(settings.db_path, source, "processing", job_id=job_id)
    try:
        chunks = parse_url(url, source=source)
        if not chunks:
            raise ValueError("Tidak ada teks yang bisa diekstrak dari URL.")
        n = _index_chunks(settings, store, source, category, chunks, job_id=job_id)
        db.update_document_status(
            settings.db_path, source, "ready",
            chunks=n, checksum="", category=category, job_id=job_id,
        )
        metrics["total"] += 1
        metrics["ready"] += 1
        logger.info("ingest-url: %s terindeks (%d chunk)", source, n)
    except Exception as exc:
        logger.exception("ingest-url gagal: %s", url)
        db.update_document_status(
            settings.db_path, source, "error",
            error=str(exc)[:500], job_id=job_id,
        )
        metrics["failed"] += 1
    finally:
        metrics["pending"] -= 1


def _watch_folder_loop(settings: Settings, store: VectorStore) -> None:
    """Loop asinkron: index otomatis file baru di upload_dir (fitur #6)."""
    import asyncio

    async def loop() -> None:
        while True:
            try:
                await asyncio.sleep(WATCH_FOLDER_INTERVAL_SEC)
                indexed = {d["source"] for d in store.list_documents()}
                deleted = {d["source"] for d in db.list_deleted_documents(settings.db_path)}
                pending = scan_pending(settings.upload_dir, indexed | deleted)
                for path in pending:
                    source = path.name
                    cat = get_category_for_path(settings.upload_dir, path)
                    chunks = parse_any(path, source=source)
                    if not chunks:
                        continue
                    _index_chunks(settings, store, source, cat, chunks)
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
async def auth_middleware(request, call_next):
    """Fail-closed auth (P0-02): bila API_TOKEN diset, semua route API
    kecuali PUBLIC_API_PATHS wajib mengirim `Authorization: Bearer <token>`.

    SPA statis (dilayani spa_fallback) tetap publik; gerbang UI penuh
    (mis. Cloudflare Access) tetap tanggung jawab deployment. Ini memastikan
    port 8000 yang terekspos tidak bisa dipakai baca/tulis data tanpa token.
    """
    settings = getattr(request.app.state, "settings", None)
    token = settings.api_token if settings is not None else ""
    if token and _is_protected_api(request.scope):
        header = request.headers.get("Authorization", "")
        provided = header[7:].strip() if header.startswith("Bearer ") else ""
        if not provided or not hmac.compare_digest(provided, token):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Unauthorized: Authorization header (Bearer token) diperlukan."
                },
                headers={"WWW-Authenticate": "Bearer"},
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

    # Observability ringan (P2-05): counter request + rolling latensi.
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        metrics["requests"] += 1
        metrics["latency_ms"].append(duration_ms)

    # Audit log (P0-02): aksi pada route API yang terproteksi.
    if _is_protected_api(request.scope):
        settings = getattr(request.app.state, "settings", None)
        if settings is not None:
            ip = request.client.host if request.client else "unknown"
            header = request.headers.get("Authorization", "")
            actor = "token" if header.startswith("Bearer ") else ip
            db.record_audit(
                settings.db_path,
                actor,
                f"{request.method} {request.url.path}",
                ip=ip,
                status=response.status_code,
                duration_ms=duration_ms,
            )
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
    """Health check publik (dipakai systemd / load balancer)."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Metrik operasional: counter, latensi p50/p95, disk, ingestion."""
    m = dict(getattr(app.state, "metrics", {}))
    latency = m.pop("latency_ms", None)
    if latency:
        vals = sorted(latency)
        m["latency_ms_p50"] = round(statistics.median(vals), 1)
        m["latency_ms_p95"] = round(vals[int(len(vals) * 0.95) - 1], 1)
    m["latency_ms_window"] = len(latency or [])
    if hasattr(app.state, "started_at"):
        m["uptime_sec"] = round(time.time() - app.state.started_at, 1)
    # Kesehatan disk untuk data lokal (target observability P2-05).
    try:
        settings: Settings = app.state.settings
        usage = shutil.disk_usage(settings.persist_dir)
        m["disk"] = {
            "persist_free_mb": round(usage.free / (1024 * 1024), 1),
            "persist_total_mb": round(usage.total / (1024 * 1024), 1),
        }
    except Exception:
        pass
    return m


@app.get("/audit")
def audit_log(limit: int = 50) -> dict:
    """Audit log aksi API terproteksi (P0-02). Hanya lewat token."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "entries": db.list_audit(settings.db_path, limit=limit),
    }


# ----------------------------------------------------------------------
# Privasi (P0-03) — disclosure, retensi, dan hapus data pribadi
# ----------------------------------------------------------------------
@app.get("/privacy/info")
def privacy_info() -> dict:
    """Disclosure data flow: ke mana dokumen/chat dikirim, retensi, dll.

    Dipakai frontend untuk banner disclosure saat konfigurasi pertama.
    """
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "provider_label": settings.llm_provider_label,
        "external_data_flow": True,  # LLM eksternal dipakai untuk RAG
        "redaction_enabled": settings.redaction_enabled,
        "retention": {
            "chat_days": settings.retain_chat_days,
            "cache_max_days": settings.cache_max_days,
        },
        "disclosure_text": (
            f"Aplikasi ini mengirim isi dokumen yang relevan dan riwayat chat "
            f"ke {settings.llm_provider_label} untuk menghasilkan jawaban. "
            "Data tersimpan lokal (ChromaDB + SQLite) di mesin ini."
            + (
                " Redaksi PII aktif: email/nomor telepon/pola rahasia "
                "disensor sebelum dikirim ke LLM."
                if settings.redaction_enabled
                else ""
            )
            + (
                f" Chat yang tidak diakses lebih dari {settings.retain_chat_days} hari "
                "dihapus otomatis."
                if settings.retain_chat_days > 0
                else " Chat disimpan tanpa batas waktu sampai kamu menghapusnya."
            )
        ),
    }


@app.delete("/privacy/data")
def privacy_clear_all() -> dict:
    """Hapus SEMUA data pribadi termasuk dokumen terindeks (total wipe).

    Membersihkan SQLite (chat, kuis, kartu, glossary, anotasi, registry
    dokumen) + ChromaDB (seluruh chunk dokumen & semantic cache) + file
    fisik upload (agar watch-folder tidak meng-indeks ulang).
    """
    settings: Settings = app.state.settings
    store: VectorStore = app.state.store
    deleted = db.clear_all_user_data(settings.db_path)
    # ChromaDB: buang seluruh chunk dokumen + semantic cache jawaban.
    try:
        store.reset()
        deleted["chroma_documents"] = store.count()
    except Exception:
        logger.exception("privacy: gagal reset indeks dokumen")
        deleted["chroma_documents"] = -1
    try:
        from app.semantic_cache import SemanticCache

        deleted["semantic_cache"] = SemanticCache(store).clear()
    except Exception:
        logger.exception("privacy: gagal bersihkan semantic cache")
        deleted["semantic_cache"] = -1
    # File fisik upload + staging: tanpa ini watch-folder akan meng-indeks
    # ulang dokumen yang baru saja dihapus.
    deleted["upload_files"] = _purge_dir_files(settings.upload_dir)
    deleted["staging_files"] = _purge_dir_files(settings.staging_dir)
    logger.warning("privacy: semua data pribadi dihapus: %s", deleted)
    return {"status": "ok", "deleted": deleted}


def _purge_dir_files(directory: Path) -> int:
    """Hapus semua file di dalam direktori (rekursif). Return jumlah file."""
    if not directory.exists():
        return 0
    removed = 0
    for f in directory.rglob("*"):
        if f.is_file():
            _safe_unlink(f, attempts=2)
            removed += 1
    return removed


@app.delete("/privacy/cache")
def privacy_clear_cache() -> dict:
    """Kosongkan semantic cache (jawaban LLM tersimpan)."""
    store: VectorStore = app.state.store
    from app.semantic_cache import SemanticCache

    n = SemanticCache(store).clear()
    return {"status": "ok", "cleared_entries": n}


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
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
) -> dict:
    """Upload dokumen -> job ingestion asinkron (P1-01).

    Response langsung berisi job_id; klien mem-poll GET /jobs/{job_id}.
    File ditulis ke staging dulu, baru dipindah ke upload_dir setelah
    parsing sukses. Re-upload dengan checksum sama dilewati (dedup).
    """
    settings: Settings = app.state.settings
    filename = Path(file.filename or "file.pdf").name  # cegah path traversal
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format tidak didukung: {ext}. Gunakan {sorted(SUPPORTED_EXTENSIONS)}.",
        )

    content = file.file.read()
    try:
        file.file.close()  # lepaskan handle upload (Windows file lock)
    except Exception:
        pass
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail=f"File maksimal {MAX_UPLOAD_MB} MB."
        )
    if ext == ".pdf" and not content.lstrip().startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid.")

    src = source or filename
    cat = category.strip() if category and category.strip() else "Umum"
    checksum = hashlib.sha256(content).hexdigest()

    # Dedup: versi ready dengan konten sama -> tidak perlu diproses ulang.
    existing = db.get_document(settings.db_path, src)
    if (
        existing
        and existing.get("status") == "ready"
        and existing.get("checksum") == checksum
    ):
        logger.info("upload: %s tidak berubah (checksum sama), dilewati", src)
        return {
            "status": "ready",
            "unchanged": True,
            "source": src,
            "category": cat,
            "kind": ext.lstrip("."),
            "chunks": existing.get("chunks", 0),
        }

    job_id = uuid.uuid4().hex
    staged = settings.staging_dir / f"{job_id}_{filename}"
    staged.write_bytes(content)
    db.register_document(
        settings.db_path, src, kind="file", job_id=job_id,
        file_path="", checksum=checksum, size_bytes=len(content),
        category=cat, status="queued",
    )
    background_tasks.add_task(
        _ingest_file_job, settings, app.state.store,
        staged, src, cat, ext.lstrip("."), job_id, checksum,
    )
    return {
        "status": "processing",
        "job_id": job_id,
        "source": src,
        "category": cat,
        "kind": ext.lstrip("."),
    }


@app.post("/ingest-url")
def ingest_url(
    req: IngestUrlRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
) -> dict:
    """Index konten dari URL sebagai job asinkron (fitur #15, P1-01).

    Fetch jaringan + parse dijalankan di background (threadpool) supaya
    request tidak memblokir worker; klien mem-poll GET /jobs/{job_id}.
    """
    settings: Settings = app.state.settings
    src = req.source or req.url
    cat = req.category.strip() if req.category and req.category.strip() else "Umum"
    job_id = uuid.uuid4().hex
    db.register_document(
        settings.db_path, src, kind="url", job_id=job_id,
        category=cat, status="queued",
    )
    background_tasks.add_task(
        _ingest_url_job, settings, app.state.store,
        req.url, src, cat, job_id,
    )
    return {
        "status": "processing",
        "job_id": job_id,
        "source": src,
        "category": cat,
        "kind": "url",
    }


@app.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    """Status job ingestion (P1-01): queued|processing|ready|error."""
    settings: Settings = app.state.settings
    doc = db.get_document_by_job(settings.db_path, job_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return {"status": "ok", "job": doc}


@app.get("/jobs")
def jobs_list(limit: int = 20) -> dict:
    """Daftar job ingestion terbaru (untuk UI progress/monitoring)."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "jobs": db.list_document_registry(settings.db_path)[:limit],
    }


def _prepare_query(engine: RAGEngine, settings: Settings, req: QueryRequest) -> dict:
    """Bangun konteks query: filter, history, session, summary, grounding.

    Dipakai bersama oleh /query dan /query/stream (P1-05) supaya tidak ada
    duplikasi logika — policy query (filter, session, grounding) selalu
    sinkron di kedua endpoint.
    """
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
    missing: dict | None = None
    if req.source:
        status = engine.document_status(req.source, settings.db_path)
        if not status["exists"]:
            hint = (
                "sudah dihapus dari indeks"
                if status["deleted"]
                else "belum pernah diindeks"
            )
            detail = (
                f"Dokumen '{req.source}' {hint}. Dokumen yang aktif: "
                f"{', '.join(status['available']) or 'tidak ada'}."
            )
            missing = {"detail": detail, "session_info": session_info}

    return {
        "where": where,
        "history": history,
        "session_info": session_info,
        "summary": summary,
        "missing": missing,
    }


@app.post("/query")
def query(req: QueryRequest) -> dict:
    """Tanya jawab berdasarkan dokumen terindeks (+ konteks session bila ada)."""
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    ctx = _prepare_query(engine, settings, req)

    if ctx["missing"]:
        missing = ctx["missing"]
        if ctx["session_info"] is not None:
            db.add_message(settings.db_path, req.session_id, "user", req.question, [])
            db.add_message(
                settings.db_path, req.session_id, "assistant", missing["detail"], []
            )
        return {
            "status": "ok",
            "answer": missing["detail"],
            "cached": False,
            "model": None,
            "sources": [],
            "grounded": False,
            "document_missing": True,
            "session": ctx["session_info"],
        }

    # Simpan pertanyaan user SEBELUM call LLM (auto-title butuh pesan pertama)
    if ctx["session_info"] is not None:
        db.add_message(settings.db_path, req.session_id, "user", req.question, [])

    try:
        answer = engine.query(
            req.question,
            top_k=req.top_k,
            where=ctx["where"],
            history=ctx["history"],
            summary=ctx["summary"],
        )
    except LLMError as exc:
        app.state.metrics["llm_errors"] += 1
        # from None: detail error internal tidak perlu dirantai ke traceback
        raise HTTPException(status_code=502, detail=str(exc)) from None
    _record_query(app.state.metrics, answer.cached)

    # Simpan jawaban + update session
    session_info = ctx["session_info"]
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
    ctx = _prepare_query(engine, settings, req)
    session_info = ctx["session_info"]

    if ctx["missing"]:
        missing = ctx["missing"]
        if session_info is not None:
            db.add_message(settings.db_path, req.session_id, "user", req.question, [])
            db.add_message(
                settings.db_path, req.session_id, "assistant", missing["detail"], []
            )
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
            yield _sse({"type": "delta", "text": missing["detail"]})
            yield _sse({"type": "done", "answer": missing["detail"], "session": session_info})

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
                where=ctx["where"],
                history=ctx["history"],
                summary=ctx["summary"],
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
# Glossary (istilah + definisi yang dapat diverifikasi user)
# ----------------------------------------------------------------------
class GlossaryRequest(BaseModel):
    term: str = Field(..., min_length=1, max_length=160)
    definition: str = Field(..., min_length=1, max_length=3000)
    source: str | None = Field(default=None, max_length=300)
    page: int | None = Field(default=None, ge=1, le=1_000_000)
    category: str = Field(default="Umum", min_length=1, max_length=100)
    verified: bool = False


class GlossaryExtractRequest(BaseModel):
    source: str | None = Field(default=None, max_length=300)
    n: int = Field(default=10, ge=1, le=20)


@app.get("/glossary")
@app.get("/api/glossary")
def list_glossary(
    q: str = "",
    search: str = "",
    source: str | None = None,
    verified: bool | None = None,
    limit: int = 100,
) -> dict:
    settings: Settings = app.state.settings
    query_term = q or search
    return {
        "status": "ok",
        "terms": db.list_glossary(
            settings.db_path, search=query_term, source=source, verified=verified, limit=limit
        ),
    }


@app.get("/glossary/candidates")
@app.get("/api/glossary/candidates")
def get_glossary_candidates(source: str | None = None, limit: int = 10) -> dict:
    """Ambil kandidat glossary dari dokumen via GET."""
    engine: RAGEngine = app.state.engine
    try:
        candidates = glossary.extract_candidates(engine, source=source, limit=limit)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return {
        "status": "ok",
        "source": source,
        "candidates": candidates,
        "review_required": True,
    }


@app.post("/glossary/extract")
@app.post("/api/glossary/extract")
def extract_glossary(req: GlossaryExtractRequest) -> dict:
    """Usulkan kandidat glossary dari dokumen; belum disimpan sebelum direview user."""
    engine: RAGEngine = app.state.engine
    try:
        candidates = glossary.extract_candidates(engine, source=req.source, limit=req.n)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return {
        "status": "ok",
        "source": req.source,
        "candidates": candidates,
        "review_required": True,
    }


@app.post("/glossary", status_code=201)
@app.post("/api/glossary", status_code=201)
def create_glossary(req: GlossaryRequest) -> dict:
    settings: Settings = app.state.settings
    try:
        term = db.create_glossary_term(
            settings.db_path,
            req.term,
            req.definition,
            req.source or "",
            req.page,
            req.category,
            req.verified,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Istilah tersebut sudah ada.") from None
    return {"status": "ok", "term": term}


@app.put("/glossary/{term_id}")
@app.put("/api/glossary/{term_id}")
def update_glossary(term_id: int, req: GlossaryRequest) -> dict:
    settings: Settings = app.state.settings
    try:
        term = db.update_glossary_term(
            settings.db_path,
            term_id,
            req.term,
            req.definition,
            req.source or "",
            req.page,
            req.category,
            req.verified,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Istilah tersebut sudah ada.") from None
    if term is None:
        raise HTTPException(status_code=404, detail="Istilah tidak ditemukan.")
    return {"status": "ok", "term": term}


@app.put("/glossary/{term_id}/verify")
@app.put("/api/glossary/{term_id}/verify")
def toggle_verify_glossary(term_id: int) -> dict:
    """Toggle status verifikasi istilah glosarium (Terverifikasi <-> Draf)."""
    settings: Settings = app.state.settings
    with db._conn(settings.db_path) as conn:
        row = conn.execute(
            "SELECT * FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Istilah tidak ditemukan.")
        new_val = 0 if row["verified"] else 1
        conn.execute(
            "UPDATE glossary_terms SET verified = ?, updated_at = ? WHERE id = ?",
            (new_val, db._now(), term_id),
        )
        updated = conn.execute(
            "SELECT * FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone()
    return {"status": "ok", "term": {**dict(updated), "verified": bool(updated["verified"])}}


@app.delete("/glossary/{term_id}")
@app.delete("/api/glossary/{term_id}")
def delete_glossary(term_id: int) -> dict:
    settings: Settings = app.state.settings
    if not db.delete_glossary_term(settings.db_path, term_id):
        raise HTTPException(status_code=404, detail="Istilah tidak ditemukan.")
    return {"status": "ok", "term_id": term_id}


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


@app.put("/documents/{source:path}/category")
def set_document_category(source: str, req: SetCategoryRequest) -> dict:
    settings: Settings = app.state.settings
    store: VectorStore = app.state.store
    cat = req.category.strip() or "Umum"
    db.set_document_category(settings.db_path, source, cat)
    db.update_document_status(settings.db_path, source, category=cat)
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


@app.delete("/documents/{source:path}")
def delete_document(source: str, purge: bool = False) -> dict:
    """Hapus dokumen dari indeks dan database."""
    store: VectorStore = app.state.store
    settings: Settings = app.state.settings
    doc_exists = bool(db.get_document(settings.db_path, source))
    removed = store.delete_document(source)
    if removed == 0 and not doc_exists:
        raise HTTPException(
            status_code=404, detail=f"Dokumen '{source}' tidak ditemukan."
        )
    
    # Catat ke deleted documents agar grounding & watch-folder tahu
    db.record_deleted_document(settings.db_path, source)
    
    # Hapus file fisik dari folder uploads jika ada agar tidak re-indeks otomatis
    try:
        cand1 = settings.upload_dir / source
        if cand1.exists() and cand1.is_file():
            cand1.unlink(missing_ok=True)
            logger.info("purge: physical file deleted: %s", cand1)
        cand2 = settings.upload_dir / Path(source).name
        if cand2.exists() and cand2.is_file():
            cand2.unlink(missing_ok=True)
            logger.info("purge: physical file deleted: %s", cand2)
    except Exception as exc:
        logger.warning("purge file error: %s", exc)

    # Bersihkan dari registry DB dan kategori
    db.delete_document_category_mapping(settings.db_path, source)
    db.purge_document(settings.db_path, source)

    return {"status": "ok", "source": source, "removed": removed, "purged": True}


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Learning loop — review mode, weak-spot, progress, quiz, flashcards
# ----------------------------------------------------------------------
@app.get("/learning/due")
@app.get("/api/learning/due")
def learning_due(source: str | None = None, limit: int = 20) -> dict:
    """Kartu yang sudah waktunya diulang (SM-2 scheduler)."""
    settings: Settings = app.state.settings
    learning.sync_cards(settings.db_path)
    return {
        "status": "ok",
        "cards": learning.due_cards(settings.db_path, source=source, limit=limit),
        "stats": learning.card_stats(settings.db_path, source=source),
    }


@app.post("/learning/answer")
@app.post("/api/learning/answer")
def learning_answer(req: AnswerCardRequest) -> dict:
    """Catat jawaban kartu review SM-2: remembered=True / rating 1-4."""
    settings: Settings = app.state.settings
    rating_val = req.rating if req.rating is not None else req.remembered
    try:
        card = learning.answer_card(
            settings.db_path, req.card_id, rating_val
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {"status": "ok", "card": card}


@app.get("/learning/cards")
@app.get("/api/learning/cards")
def learning_list_cards(source: str | None = None, limit: int = 100) -> dict:
    """Daftar seluruh kartu di review_cards."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "cards": learning.list_review_cards(settings.db_path, source=source, limit=limit),
        "stats": learning.card_stats(settings.db_path, source=source),
    }


@app.post("/learning/flashcards/generate")
@app.post("/api/learning/flashcards/generate")
def learning_flashcards_generate(req: FlashcardGenerateRequest) -> dict:
    """Generate high-yield Active Recall Q&A Flashcards using LLM."""
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    try:
        cards = learning.generate_flashcards(engine, source=req.source, n=req.n)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    if not cards:
        raise HTTPException(
            status_code=400, detail="Tidak ada materi untuk membuat flashcard."
        )

    saved = []
    if req.save_to_deck:
        saved = learning.save_flashcards_to_deck(settings.db_path, cards)

    return {
        "status": "ok",
        "source": req.source,
        "cards": cards,
        "saved_cards": saved,
    }


@app.post("/learning/flashcards/custom")
@app.post("/api/learning/flashcards/custom")
def learning_flashcards_custom(req: CustomCardRequest) -> dict:
    """Buat kartu review manual custom."""
    settings: Settings = app.state.settings
    card = learning.create_custom_card(
        settings.db_path, req.question, req.answer, req.source
    )
    return {"status": "ok", "card": card}


@app.delete("/learning/flashcards/{card_id}")
@app.delete("/api/learning/flashcards/{card_id}")
def learning_flashcards_delete(card_id: str) -> dict:
    """Hapus kartu review dari dek."""
    settings: Settings = app.state.settings
    if not learning.delete_review_card(settings.db_path, card_id):
        raise HTTPException(status_code=404, detail="Kartu tidak ditemukan.")
    return {"status": "ok", "card_id": card_id}


@app.get("/learning/recommendations")
@app.get("/api/learning/recommendations")
def learning_get_recommendations() -> dict:
    """Rekomendasi belajar cerdas dan aksi perbaikan weak-spots."""
    settings: Settings = app.state.settings
    return learning.learning_recommendations(settings.db_path)


@app.get("/learning/weak-spots")
@app.get("/api/learning/weak-spots")
def learning_weak_spots(limit: int = 8) -> dict:
    """Topik yang paling sering diulang / sering lupa (#2, P2-03)."""
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "weak_spots": learning.weak_spots(settings.db_path, limit=limit),
        "mastery": learning.mastery_stats(settings.db_path),
    }


@app.get("/learning/mastery")
@app.get("/api/learning/mastery")
def learning_mastery() -> dict:
    """Mastery per dokumen: exposure vs correctness (P2-03).

    Dipakai halaman Progress (learningService.getMastery).
    """
    settings: Settings = app.state.settings
    return {"status": "ok", "mastery": learning.mastery_stats(settings.db_path)}


@app.get("/learning/mindmap")
@app.get("/api/learning/mindmap")
def learning_mindmap(source: str | None = None) -> dict:
    """Peta konsep (tree) dari heading dokumen terindeks."""
    store: VectorStore = app.state.store
    return {"status": "ok", "mindmap": learning.mindmap_tree(store, source=source)}


@app.get("/learning/summary")
@app.get("/api/learning/summary")
def learning_summary(source: str) -> dict:
    """Ringkasan otomatis satu dokumen via LLM."""
    engine: RAGEngine = app.state.engine
    return {
        "status": "ok",
        "source": source,
        "summary": learning.document_summary(engine, source),
    }


@app.get("/learning/progress")
@app.get("/api/learning/progress")
def learning_progress() -> dict:
    """Bab per dokumen yang sudah/belum dibahas (#3).

    Key `progress` dipakai frontend; `documents` dipertahankan untuk
    kompatibilitas konsumen lama.
    """
    settings: Settings = app.state.settings
    docs = learning.document_progress(settings.db_path)
    return {"status": "ok", "documents": docs, "progress": docs}


@app.post("/learning/quiz/generate")
@app.post("/api/learning/quiz/generate")
def learning_quiz_generate(req: QuizGenerateRequest) -> dict:
    """Buat soal pilihan ganda dari materi (#4, P2-04)."""
    engine: RAGEngine = app.state.engine
    settings: Settings = app.state.settings
    try:
        questions = learning.generate_quiz(engine, source=req.source, n=req.n)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    if not questions:
        raise HTTPException(
            status_code=400, detail="Tidak ada materi untuk membuat soal."
        )
    attempt = learning.create_quiz_attempt(settings.db_path, req.source, questions)
    return {
        "status": "ok",
        "attempt_id": attempt["attempt_id"],
        "source": attempt["source"],
        "questions": attempt["questions"],
    }


@app.post("/learning/quiz/grade")
@app.post("/api/learning/quiz/grade")
def learning_quiz_grade(req: QuizGradeRequest) -> dict:
    """Koreksi jawaban kuis secara DETERMINISTIK dari kunci server (P2-04).

    Pembahasan per soal dihasilkan LLM (opsional, tidak mengubah skor);
    bila LLM gagal, hasil tetap dikembalikan tanpa pembahasan.
    """
    settings: Settings = app.state.settings
    engine: RAGEngine = app.state.engine
    try:
        result = learning.grade_quiz_attempt(
            settings.db_path, req.attempt_id, req.answers
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    explanations = learning.explain_quiz_questions(
        engine, settings.db_path, req.attempt_id, req.answers
    )
    if explanations:
        for i, detail in enumerate(result["details"]):
            if i < len(explanations):
                detail["explanation"] = explanations[i]
    return {"status": "ok", **result}


@app.get("/learning/quiz/history")
@app.get("/api/learning/quiz/history")
def learning_quiz_history(limit: int = 20) -> dict:
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "history": learning.quiz_history(settings.db_path, limit=limit),
    }


@app.get("/learning/quiz/attempts/{attempt_id}")
@app.get("/api/learning/quiz/attempts/{attempt_id}")
def learning_quiz_attempt_detail(attempt_id: str) -> dict:
    """Pembahasan ulang: soal + kunci jawaban satu attempt kuis (dari riwayat)."""
    settings: Settings = app.state.settings
    detail = learning.quiz_attempt_detail(settings.db_path, attempt_id)
    if detail is None:
        raise HTTPException(
            status_code=404, detail="Attempt kuis tidak ditemukan."
        )
    return {"status": "ok", **detail}


@app.get("/learning/flashcards")
@app.get("/api/learning/flashcards")
def learning_flashcards(
    source: str | None = None, limit: int = 20, refresh: bool = False
) -> dict:
    """Kartu Q&A untuk tab Eksplorasi Dokumen.

    Prioritas: LLM menentukan konten (konsep/pertanyaan + penjelasan
    ringkas, di-cache per sumber), fallback heading/chunk bila LLM tidak
    tersedia. `refresh=true` memaksa regenerasi (lewati cache).
    """
    settings: Settings = app.state.settings
    store: VectorStore = app.state.store
    engine: RAGEngine = app.state.engine
    return {
        "status": "ok",
        "cards": learning.flashcards(
            store,
            source=source,
            limit=limit,
            engine=engine,
            db_path=settings.db_path,
            force=refresh,
        ),
    }


@app.post("/learning/flashcards/answer")
@app.post("/api/learning/flashcards/answer")
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
@app.get("/api/learning/flashcards/stats")
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
