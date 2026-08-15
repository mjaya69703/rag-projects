"""Chat Controller handling Q&A, streaming, and session history."""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.Http.Requests.ChatRequests import QueryRequest, RenameRequest, SessionCreateRequest
from app.Repositories.SessionRepository import SessionRepository
from app.Services.RagService import RagService

router = APIRouter(tags=["Chat"])


def get_session_repo(request: Request) -> SessionRepository:
    return SessionRepository(db_path=request.app.state.settings.db_path)


def get_rag_service(request: Request) -> RagService:
    return request.app.state.engine


@router.post("/query")
def query_endpoint(
    req: QueryRequest,
    request: Request,
    session_repo: SessionRepository = Depends(get_session_repo),
    rag: RagService = Depends(get_rag_service),
) -> dict:
    where = {}
    if req.source:
        where["source"] = req.source
    if req.category:
        where["category"] = req.category
    where_filter = where if where else None

    session_id = req.session_id
    history = []
    summary_text = None

    if session_id:
        sess = session_repo.get_session(session_id)
        if not sess:
            sess = session_repo.create_session(title="New Chat")
            session_id = sess["id"]

        if req.mode == "summary":
            summary_row = session_repo.get_summary(session_id)
            summary_text = summary_row["summary_text"] if summary_row else None
            history = session_repo.get_messages(session_id, limit=5)
        else:
            history = session_repo.get_messages(session_id, limit=req.history_n)

    answer = rag.query(
        question=req.question,
        top_k=req.top_k,
        where=where_filter,
        history=history,
        summary=summary_text,
    )

    if session_id:
        session_repo.add_message(session_id, role="user", content=req.question)
        sources_meta = [
            {
                "source": s.source,
                "page": s.page,
                "heading": s.heading,
                "distance": s.distance,
                "chunk_index": s.chunk_index,
            }
            for s in answer.sources
        ]
        session_repo.add_message(
            session_id,
            role="assistant",
            content=answer.answer,
            sources=sources_meta,
        )

        cnt = session_repo.get_message_count(session_id)
        if cnt == 2:
            new_title = rag.generate_title(req.question)
            session_repo.rename_session(session_id, new_title)

    return {
        "answer": answer.answer,
        "sources": [
            {
                "source": s.source,
                "page": s.page,
                "heading": s.heading,
                "distance": s.distance,
                "chunk_index": s.chunk_index,
            }
            for s in answer.sources
        ],
        "cached": answer.cached,
        "model": answer.model,
        "session_id": session_id,
        "grounded": answer.grounded,
    }


@router.post("/query/stream")
async def query_stream_endpoint(
    req: QueryRequest,
    request: Request,
    session_repo: SessionRepository = Depends(get_session_repo),
    rag: RagService = Depends(get_rag_service),
):
    where = {}
    if req.source:
        where["source"] = req.source
    if req.category:
        where["category"] = req.category
    where_filter = where if where else None

    session_id = req.session_id
    history = []
    summary_text = None

    if session_id:
        sess = session_repo.get_session(session_id)
        if not sess:
            sess = session_repo.create_session(title="New Chat")
            session_id = sess["id"]

        if req.mode == "summary":
            summary_row = session_repo.get_summary(session_id)
            summary_text = summary_row["summary_text"] if summary_row else None
            history = session_repo.get_messages(session_id, limit=5)
        else:
            history = session_repo.get_messages(session_id, limit=req.history_n)

    async def event_generator():
        collected_parts = []
        sources_meta = []

        async for event in rag.stream_query(
            question=req.question,
            top_k=req.top_k,
            where=where_filter,
            history=history,
            summary=summary_text,
        ):
            if event["type"] == "meta":
                sources_meta = [
                    {
                        "source": s.source,
                        "page": s.page,
                        "heading": s.heading,
                        "distance": s.distance,
                        "chunk_index": s.chunk_index,
                    }
                    for s in event.get("sources", [])
                ]
                event["session_id"] = session_id
                event["sources"] = sources_meta
            elif event["type"] == "delta":
                collected_parts.append(event["text"])
            
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        full_answer = "".join(collected_parts)
        if session_id and full_answer:
            session_repo.add_message(session_id, role="user", content=req.question)
            session_repo.add_message(
                session_id,
                role="assistant",
                content=full_answer,
                sources=sources_meta,
            )
            cnt = session_repo.get_message_count(session_id)
            if cnt == 2:
                new_title = rag.generate_title(req.question)
                session_repo.rename_session(session_id, new_title)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sessions/create")
def create_session_endpoint(
    req: SessionCreateRequest,
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict:
    sess = session_repo.create_session(title=req.title)
    return {"status": "ok", "session": sess}


@router.get("/sessions/list")
def list_sessions_endpoint(
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict:
    sessions = session_repo.list_sessions()
    return {"status": "ok", "sessions": sessions}


@router.get("/sessions/{session_id}/messages")
def get_session_messages_endpoint(
    session_id: str,
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict:
    sess = session_repo.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
    messages = session_repo.get_messages(session_id)
    return {"status": "ok", "messages": messages}


@router.put("/sessions/{session_id}/rename")
def rename_session_endpoint(
    session_id: str,
    req: RenameRequest,
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict:
    ok = session_repo.rename_session(session_id, req.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
    return {"status": "ok"}


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(
    session_id: str,
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict:
    ok = session_repo.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan.")
    return {"status": "ok"}
