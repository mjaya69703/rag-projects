"""Learning Loop Controller for Spaced Repetition, Quizzes, Flashcards, and Progress."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.Http.Requests.LearningRequests import (
    AnswerCardRequest,
    FlashcardAnswerRequest,
    QuizGenerateRequest,
    QuizGradeRequest,
)
from app.Repositories.LearningRepository import LearningRepository
from app.Repositories.SessionRepository import SessionRepository
from app.Services.LearningService import LearningService

router = APIRouter(prefix="/learning", tags=["Learning"])


def get_learning_service(request: Request) -> LearningService:
    db_path = request.app.state.settings.db_path
    return LearningService(
        learning_repo=LearningRepository(db_path=db_path),
        vector_repo=request.app.state.store,
        llm=request.app.state.engine.llm,
        session_repo=SessionRepository(db_path=db_path),
    )


@router.get("/due")
def due_cards_endpoint(
    limit: int = 10,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    cards = learning.due_cards(limit=limit)
    stats = learning.card_stats()
    return {"status": "ok", "cards": cards, "stats": stats}


@router.post("/answer")
def answer_card_endpoint(
    req: AnswerCardRequest,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    try:
        updated = learning.answer_card(req.card_id, req.remembered)
        return {"status": "ok", "card": updated}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/quiz/generate")
def quiz_generate_endpoint(
    req: QuizGenerateRequest,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    questions = learning.generate_quiz(source=req.source, n=req.n)
    if not questions:
        raise HTTPException(status_code=400, detail="Tidak cukup materi untuk membuat kuis.")
    attempt = learning.create_quiz_attempt(source=req.source, questions=questions)
    return {"status": "ok", **attempt}


@router.post("/quiz/grade")
def quiz_grade_endpoint(
    req: QuizGradeRequest,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    try:
        result = learning.grade_quiz_attempt(req.attempt_id, req.answers)
        return {"status": "ok", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/quiz/history")
def quiz_history_endpoint(
    limit: int = 20,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    history = learning.quiz_history(limit=limit)
    return {"status": "ok", "history": history}


@router.get("/flashcards")
def flashcards_endpoint(
    source: str | None = None,
    limit: int = 20,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    cards = learning.flashcards(source=source, limit=limit)
    return {"status": "ok", "cards": cards}


@router.post("/flashcards/answer")
def flashcards_answer_endpoint(
    req: FlashcardAnswerRequest,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    stat = learning.answer_flashcard(req.heading, req.source, req.known)
    return {"status": "ok", "stat": stat}


@router.get("/flashcards/stats")
def flashcards_stats_endpoint(
    limit: int = 50,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    stats = learning.flashcard_stats(limit=limit)
    return {"status": "ok", "stats": stats}


@router.get("/weak-spots")
def weak_spots_endpoint(
    limit: int = 8,
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    spots = learning.weak_spots(limit=limit)
    return {"status": "ok", "weak_spots": spots}


@router.get("/mastery")
def mastery_endpoint(
    learning: LearningService = Depends(get_learning_service),
) -> dict:
    mastery = learning.mastery_stats()
    return {"status": "ok", "mastery": mastery}


@router.get("/progress")
def progress_endpoint(
    request: Request,
) -> dict:
    from app import learning as learning_module
    db_path = request.app.state.settings.db_path
    vector_repo = request.app.state.store
    docs = vector_repo.list_all_documents()
    headings_by_source = {}
    for d in docs:
        chunks = vector_repo.get_by_source(d)
        headings_by_source[d] = [
            c.get("metadata", {}).get("heading", "") for c in chunks
        ]
    progress = learning_module.document_progress(db_path, headings_by_source)
    return {"status": "ok", "progress": progress}
