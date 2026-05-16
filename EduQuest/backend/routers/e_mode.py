from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import database
import dependencies
from e_mode_documents import extract_text_from_upload, select_relevant_context
from e_mode_llm import EModeLLMError, build_e_mode_prompt, generate_draft_from_llm
from e_mode_schema import EModeValidationError, get_supported_question_types, normalize_draft
from firestore_primary_store import get_store


router = APIRouter()


def _store():
    return get_store()


class EModeSessionCreate(BaseModel):
    course_id: int
    lesson_id: int
    topic: str
    instructions: str = ""
    student_level: Optional[str] = None
    difficulty: Optional[str] = None
    language: Optional[str] = None
    task_count: Optional[int] = Field(default=None, ge=1, le=20)
    preferred_types: list[str] = Field(default_factory=list)
    quiz_title: Optional[str] = None


class EModeChatRequest(BaseModel):
    message: str


class EModeSaveRequest(BaseModel):
    title: Optional[str] = None
    xp_reward: Optional[int] = Field(default=None, ge=0, le=500)


def _ensure_teacher_session_access(session_id: int, teacher_id: int, db: Session) -> dict:
    session = _store().get_e_mode_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="E-Mode session not found")
    if session["teacher_user_id"] != teacher_id:
        raise HTTPException(status_code=404, detail="E-Mode session not found")
    return session


def _load_lesson_for_teacher(course_id: int, lesson_id: int, db: Session) -> tuple[dict, dict]:
    course = _store().get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lesson = _store().get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if lesson["course_id"] != course_id:
        raise HTTPException(status_code=400, detail="Lesson does not belong to the selected course")
    return course, lesson


def _parse_preferred_types(raw_value: str) -> list[str]:
    try:
        value = json.loads(raw_value) if raw_value else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Preferred types payload must be valid JSON") from exc
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="Preferred types must be a JSON list")
    return [str(item).strip() for item in value if str(item).strip()]


def _serialize_session(session: dict) -> dict:
    draft = json.loads(session["current_draft"]) if session.get("current_draft") else None
    preferred_types = json.loads(session.get("preferred_types") or "[]")
    recent_messages = [
        {
            "id": message["id"],
            "role": message["role"],
            "content": message["content"],
            "created_at": message["created_at"].isoformat() if message.get("created_at") else None,
        }
        for message in _store().list_e_mode_messages(session["id"])
    ]
    if session.get("extracted_material_text"):
        generation_source = "uploaded_material"
    elif session.get("lesson_content_snapshot"):
        generation_source = "lesson_content"
    else:
        generation_source = "teacher_instructions"
    return {
        "id": session["id"],
        "course_id": session["course_id"],
        "lesson_id": session["lesson_id"],
        "topic": session["topic"],
        "instructions": session.get("instructions", ""),
        "student_level": session.get("student_level"),
        "difficulty": session.get("difficulty"),
        "language": session.get("language"),
        "task_count": session.get("task_count"),
        "preferred_types": preferred_types,
        "quiz_title": session.get("quiz_title"),
        "uploaded_file_name": session.get("uploaded_file_name"),
        "uploaded_file_type": session.get("uploaded_file_type"),
        "material_ready": bool(session.get("extracted_material_text")),
        "generation_source": generation_source,
        "draft": draft,
        "messages": recent_messages,
        "supported_types": get_supported_question_types(),
        "created_at": session["created_at"].isoformat() if session.get("created_at") else None,
        "updated_at": session["updated_at"].isoformat() if session.get("updated_at") else None,
    }


def _append_message(session: dict, *, role: str, content: str, db: Session) -> None:
    _store().add_e_mode_message(
        {"session_id": session["id"], "role": role, "content": content},
        db=db,
    )


def _run_generation(
    session: dict,
    *,
    teacher_message: str,
    db: Session,
) -> dict:
    lesson = _store().get_lesson(session["lesson_id"])
    lesson_content = lesson.get("content", "") if lesson else ""
    material_text = str(session.get("extracted_material_text") or "").strip()
    lesson_content = str(session.get("lesson_content_snapshot") or lesson_content or "").strip()
    source_context = material_text or lesson_content or ""

    current_draft = json.loads(session["current_draft"]) if session.get("current_draft") else None
    recent_messages = [
        {"role": message["role"], "content": message["content"]}
        for message in _store().list_e_mode_messages(session["id"])[-4:]
    ]
    material_context = (
        select_relevant_context(
            source_context,
            topic=session["topic"],
            instructions=session.get("instructions", ""),
            latest_message=teacher_message,
        )
        if source_context
        else (
            f"Teacher topic: {session['topic']}\n"
            f"Teacher instructions: {session.get('instructions', '').strip() or 'No extra instructions.'}"
        )
    )
    prompt_messages = build_e_mode_prompt(
        topic=session["topic"],
        instructions=session.get("instructions", ""),
        student_level=session.get("student_level"),
        difficulty=session.get("difficulty"),
        language=session.get("language"),
        task_count=session.get("task_count"),
        preferred_types=json.loads(session.get("preferred_types") or "[]"),
        supported_types=get_supported_question_types(),
        draft=current_draft,
        recent_messages=recent_messages,
        material_context=material_context,
        teacher_message=teacher_message,
    )
    try:
        raw_draft = generate_draft_from_llm(prompt_messages)
        normalized = normalize_draft(
            raw_draft,
            fallback_title=session.get("quiz_title") or f"{session['topic']} Quiz",
        )
    except EModeLLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except EModeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session = _store().update_e_mode_session(
        session["id"],
        {
            "current_draft": json.dumps(
                {
                    "title": normalized.title,
                    "xp_reward": normalized.xp_reward,
                    "questions": normalized.questions,
                    "assistant_message": normalized.assistant_message,
                },
                ensure_ascii=False,
            ),
            "quiz_title": normalized.title,
        },
        db=db,
    )
    _append_message(session, role="assistant", content=normalized.assistant_message, db=db)
    session = _store().get_e_mode_session(session["id"])
    return _serialize_session(session)


@router.post("/sessions")
def create_session(
    payload: EModeSessionCreate,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.require_teacher),
):
    _, lesson = _load_lesson_for_teacher(payload.course_id, payload.lesson_id, db)
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    unsupported = set(payload.preferred_types) - set(get_supported_question_types())
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported preferred types: {', '.join(sorted(unsupported))}",
        )

    session = _store().create_e_mode_session(
        {
            "teacher_user_id": current_user.id,
            "course_id": payload.course_id,
            "lesson_id": payload.lesson_id,
            "topic": topic,
            "instructions": payload.instructions.strip(),
            "student_level": payload.student_level,
            "difficulty": payload.difficulty,
            "language": payload.language,
            "task_count": payload.task_count,
            "preferred_types": json.dumps(payload.preferred_types),
            "quiz_title": payload.quiz_title.strip() if payload.quiz_title else f"{lesson['title']} AI Draft",
            "uploaded_file_name": None,
            "uploaded_file_type": None,
            "extracted_material_text": None,
            "lesson_content_snapshot": lesson.get("content", ""),
            "current_draft": None,
        },
        db=db,
    )
    return _serialize_session(session)


@router.post("/sessions/{session_id}/upload")
def upload_material(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.require_teacher),
):
    session = _ensure_teacher_session_access(session_id, current_user.id, db)
    extracted = extract_text_from_upload(file)
    session = _store().update_e_mode_session(
        session_id,
        {
            "uploaded_file_name": file.filename,
            "uploaded_file_type": file.content_type or "application/octet-stream",
            "extracted_material_text": extracted,
        },
        db=db,
    )
    response = _serialize_session(session)
    response["extracted_char_count"] = len(extracted)
    return response


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.require_teacher),
):
    session = _ensure_teacher_session_access(session_id, current_user.id, db)
    return _serialize_session(session)


@router.post("/sessions/{session_id}/generate")
def generate_initial_draft(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.require_teacher),
):
    session = _ensure_teacher_session_access(session_id, current_user.id, db)
    teacher_message = (
        "Generate the first quiz draft from the uploaded material, topic, and instructions."
    )
    _append_message(session, role="teacher", content=teacher_message, db=db)
    db.flush()
    return _run_generation(session, teacher_message=teacher_message, db=db)


@router.post("/sessions/{session_id}/chat")
def chat_update(
    session_id: int,
    payload: EModeChatRequest,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.require_teacher),
):
    session = _ensure_teacher_session_access(session_id, current_user.id, db)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Chat message is required")
    _append_message(session, role="teacher", content=message, db=db)
    db.flush()
    return _run_generation(session, teacher_message=message, db=db)


@router.post("/sessions/{session_id}/save")
def save_draft_as_quiz(
    session_id: int,
    payload: EModeSaveRequest,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.require_teacher),
):
    session = _ensure_teacher_session_access(session_id, current_user.id, db)
    lesson = _store().get_lesson(session["lesson_id"])
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if not session.get("current_draft"):
        raise HTTPException(status_code=400, detail="Generate a draft before saving")

    try:
        raw_draft = json.loads(session["current_draft"])
        normalized = normalize_draft(
            raw_draft,
            fallback_title=session.get("quiz_title") or f"{session['topic']} Quiz",
        )
    except (json.JSONDecodeError, EModeValidationError) as exc:
        raise HTTPException(status_code=422, detail="Current draft is invalid and cannot be saved") from exc

    quiz, replaced_existing_quiz = _store().create_or_update_quiz(
        lesson_id=session["lesson_id"],
        title=((payload.title or normalized.title).strip() or normalized.title),
        xp_reward=payload.xp_reward if payload.xp_reward is not None else normalized.xp_reward,
        questions=json.dumps(normalized.questions, ensure_ascii=False),
        db=db,
    )

    return {
        "quiz": {
            "id": quiz["id"],
            "lesson_id": quiz["lesson_id"],
            "title": quiz["title"],
            "xp_reward": quiz["xp_reward"],
            "question_count": len(normalized.questions),
        },
        "session_id": session["id"],
        "saved": True,
        "replaced_existing_quiz": replaced_existing_quiz,
    }
