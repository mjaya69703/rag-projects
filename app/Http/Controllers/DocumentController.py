"""Document Controller for Uploads, URL ingestion, and Library Management."""

from __future__ import annotations

import shutil
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from app.Core.Config import MAX_UPLOAD_MB, Settings
from app.Http.Requests.DocumentRequests import IngestUrlRequest, SetCategoryRequest
from app.Repositories.DocumentRepository import DocumentRepository
from app.Repositories.VectorRepository import VectorRepository
from app.Services.IngestionService import IngestionService
from app.Services.RagService import RagService

router = APIRouter(tags=["Documents"])


def get_doc_repo(request: Request) -> DocumentRepository:
    return DocumentRepository(db_path=request.app.state.settings.db_path)


def get_vector_repo(request: Request) -> VectorRepository:
    return request.app.state.store


def get_ingest_service(request: Request) -> IngestionService:
    return IngestionService(
        vector_repo=request.app.state.store,
        document_repo=DocumentRepository(db_path=request.app.state.settings.db_path),
        settings=request.app.state.settings,
    )


@router.post("/upload")
def upload_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str | None = Form(default=None),
    category: str | None = Form(default=None),
    ingestion: IngestionService = Depends(get_ingest_service),
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")

    doc_source = source or file.filename
    doc_cat = category.strip() if category else "Umum"
    settings: Settings = request.app.state.settings

    job_id = uuid.uuid4().hex[:12]
    staging_file = settings.staging_dir / f"{job_id}_{file.filename}"
    staging_file.parent.mkdir(parents=True, exist_ok=True)

    with staging_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if staging_file.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
        staging_file.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Ukuran file melebihi batas {MAX_UPLOAD_MB}MB.")

    # Record queued status
    doc_repo.doc_upsert(
        source=doc_source,
        job_id=job_id,
        kind="file",
        file_path=str(staging_file),
        category=doc_cat,
        status="queued",
    )

    def _bg_job():
        try:
            doc_repo.doc_set_status(doc_source, "processing")
            final_path = settings.upload_dir / file.filename
            shutil.move(str(staging_file), str(final_path))
            n = ingestion.ingest_file(final_path, source=doc_source, category=doc_cat, job_id=job_id)
            doc_repo.doc_set_status(doc_source, "ready", chunks=n)
        except Exception as exc:
            staging_file.unlink(missing_ok=True)
            doc_repo.doc_set_status(doc_source, "error", error=str(exc))

    background_tasks.add_task(_bg_job)
    return {"status": "ok", "job_id": job_id, "source": doc_source}


@router.post("/ingest-url")
def ingest_url_endpoint(
    req: IngestUrlRequest,
    background_tasks: BackgroundTasks,
    ingestion: IngestionService = Depends(get_ingest_service),
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    job_id = uuid.uuid4().hex[:12]
    doc_source = req.source or req.url
    doc_cat = req.category.strip() if req.category else "Umum"

    doc_repo.doc_upsert(
        source=doc_source,
        job_id=job_id,
        kind="url",
        file_path=req.url,
        category=doc_cat,
        status="queued",
    )

    def _bg_job():
        try:
            doc_repo.doc_set_status(doc_source, "processing")
            n = ingestion.ingest_url(req.url, source=doc_source, category=doc_cat, job_id=job_id)
            doc_repo.doc_set_status(doc_source, "ready", chunks=n)
        except Exception as exc:
            doc_repo.doc_set_status(doc_source, "error", error=str(exc))

    background_tasks.add_task(_bg_job)
    return {"status": "ok", "job_id": job_id, "source": doc_source}


@router.get("/jobs/{job_id}")
def get_job_status_endpoint(
    job_id: str,
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    docs = doc_repo.doc_list()
    target = next((d for d in docs if d.get("job_id") == job_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return {"status": "ok", "job": target}


@router.get("/jobs")
def list_jobs_endpoint(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    return {"status": "ok", "jobs": doc_repo.doc_list()}


@router.get("/documents")
def list_documents_endpoint(
    vector_repo: VectorRepository = Depends(get_vector_repo),
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    indexed_sources = vector_repo.list_all_documents()
    categories = doc_repo.list_document_categories()
    registered = {d["source"]: d for d in doc_repo.doc_list()}

    docs = []
    for s in indexed_sources:
        reg = registered.get(s, {})
        docs.append(
            {
                "source": s,
                "category": categories.get(s, reg.get("category", "Umum")),
                "chunks": reg.get("chunks", 0),
                "status": reg.get("status", "ready"),
                "updated_at": reg.get("updated_at", ""),
            }
        )
    return {"status": "ok", "documents": docs}


@router.delete("/documents/{source:path}")
def delete_document_endpoint(
    source: str,
    purge: bool = False,
    ingestion: IngestionService = Depends(get_ingest_service),
) -> dict:
    deleted = ingestion.delete_document(source, purge_file=purge)
    return {"status": "ok", "deleted_chunks": deleted}


@router.put("/documents/{source:path}/category")
def set_document_category_endpoint(
    source: str,
    req: SetCategoryRequest,
    vector_repo: VectorRepository = Depends(get_vector_repo),
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    doc_repo.set_document_category(source, req.category)
    vector_repo.update_category(source, req.category)
    return {"status": "ok", "source": source, "category": req.category}


@router.get("/categories")
def list_categories_endpoint(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    return {"status": "ok", "categories": doc_repo.list_document_categories()}


@router.get("/deleted-documents")
def list_deleted_documents_endpoint(
    doc_repo: DocumentRepository = Depends(get_doc_repo),
) -> dict:
    return {"status": "ok", "deleted_documents": doc_repo.list_deleted_documents()}


@router.get("/locations")
def find_locations_endpoint(
    q: str,
    request: Request,
) -> dict:
    engine: RagService = request.app.state.engine
    locations = engine.find_locations(q)
    return {"status": "ok", "query": q, "locations": locations}
