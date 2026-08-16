"""Mindmap, Document Summary, Annotations, and Glossary Controller."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.Http.Requests.MindmapRequests import (
    CreateAnnotationRequest,
    CreateGlossaryTermRequest,
)
from app.Repositories.AnnotationRepository import AnnotationRepository
from app.Services.MindmapService import MindmapService

router = APIRouter(tags=["Knowledge Artifacts"])


def get_mindmap_service(request: Request) -> MindmapService:
    db_path = request.app.state.settings.db_path
    return MindmapService(
        annotation_repo=AnnotationRepository(db_path=db_path),
        vector_repo=request.app.state.store,
        llm=request.app.state.engine.llm,
    )


@router.get("/learning/mindmap")
def mindmap_endpoint(
    source: str | None = None,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    tree = service.generate_mindmap(source=source)
    return {"status": "ok", "mindmap": tree}


@router.get("/learning/summary")
def summary_endpoint(
    source: str,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    summary = service.summarize_document(source=source)
    return {"status": "ok", "source": source, "summary": summary}


@router.get("/annotations")
def list_annotations_endpoint(
    source: str | None = None,
    tag: str | None = None,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    items = service.list_annotations(source=source, tag=tag)
    return {"status": "ok", "annotations": items}


@router.post("/annotations")
def create_annotation_endpoint(
    req: CreateAnnotationRequest,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    item = service.add_annotation(
        source=req.source, chunk_id=req.chunk_id, text=req.text, page=req.page, tags=req.tags
    )
    return {"status": "ok", "annotation": item}


@router.delete("/annotations/{ann_id}")
def delete_annotation_endpoint(
    ann_id: str,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    ok = service.delete_annotation(ann_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Annotation tidak ditemukan.")
    return {"status": "ok"}


@router.get("/glossary")
def list_glossary_endpoint(
    search: str = "",
    source: str | None = None,
    verified: bool | None = None,
    limit: int = 100,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    terms = service.list_glossary(search=search, source=source, verified=verified, limit=limit)
    return {"status": "ok", "terms": terms}


@router.post("/glossary")
def create_glossary_endpoint(
    req: CreateGlossaryTermRequest,
    service: MindmapService = Depends(get_mindmap_service),
) -> dict:
    term = service.create_glossary_term(
        term=req.term,
        definition=req.definition,
        source=req.source,
        page=req.page,
        category=req.category,
        verified=req.verified,
    )
    return {"status": "ok", "term": term}


@router.get("/glossary/candidates")
def glossary_candidates_endpoint(
    request: Request,
    source: str | None = None,
    limit: int = 10,
) -> dict:
    from app import glossary as glossary_module
    engine = request.app.state.engine
    candidates = glossary_module.extract_candidates(engine, source=source, limit=limit)
    return {"status": "ok", "candidates": candidates}
