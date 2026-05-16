from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database
from typing import List
from pydantic import BaseModel
import json
import dependencies
from firestore_primary_store import get_store

router = APIRouter()


def _store():
    return get_store()


def _quiz_count_for_lesson(lesson_id: int) -> int:
    return len(_store().list_quizzes_for_lesson(lesson_id))


def _course_metadata(course: dict) -> dict:
    lessons = _store().list_lessons_for_course(course["id"])
    lesson_count = len(lessons)
    quiz_count = sum(_quiz_count_for_lesson(lesson["id"]) for lesson in lessons)
    effort_hours = max(1, lesson_count * 2)
    difficulty = (
        "Beginner"
        if course["id"] % 3 == 1
        else "Intermediate"
        if course["id"] % 3 == 2
        else "Advanced"
    )
    return {
        "lesson_count": lesson_count,
        "lesson_ids": [lesson["id"] for lesson in lessons],
        "quiz_count": quiz_count,
        "difficulty": difficulty,
        "estimated_effort": f"{effort_hours}-{effort_hours + 1} hrs",
    }


def _lesson_summary(lesson: dict) -> dict:
    quiz_count = _quiz_count_for_lesson(lesson["id"])
    content = lesson.get("content") or ""
    summary_source = content
    try:
        structured = json.loads(content)
        if isinstance(structured, dict):
            summary_source = (
                structured.get("hook")
                or structured.get("explanation")
                or structured.get("legacyText")
                or content
            )
    except (TypeError, json.JSONDecodeError):
        summary_source = content
    summary = str(summary_source)[:140].strip()
    if len(str(summary_source)) > 140:
        summary = f"{summary}..."
    return {
        "id": lesson["id"],
        "title": lesson["title"],
        "content": lesson["content"],
        "order": lesson["order"],
        "quiz_count": quiz_count,
        "has_quiz": quiz_count > 0,
        "estimated_minutes": 15 + (quiz_count * 5),
        "summary": summary,
    }


def _question_count(quiz: dict) -> int:
    try:
        questions = json.loads(quiz.get("questions") or "[]")
        return len(questions) if isinstance(questions, list) else 0
    except (TypeError, json.JSONDecodeError):
        return 0


def _quiz_passed(best_score: float | int | None) -> bool:
    return float(best_score or 0) >= 0.7


def _course_progress_payload(course: dict, user_id: int) -> dict:
    lessons = _store().list_lessons_for_course(course["id"])
    lesson_ids = {(lesson["id"] if lesson.get("id") is not None else 0) for lesson in lessons}
    completed_lessons = {
        item["lesson_id"]
        for item in _store().list_completed_lessons_for_user(user_id)
        if item.get("lesson_id") in lesson_ids
    }

    quizzes = []
    for lesson in lessons:
        quizzes.extend(_store().list_quizzes_for_lesson(lesson["id"]))
    quiz_ids = {(quiz["id"] if quiz.get("id") is not None else 0) for quiz in quizzes}
    user_attempts = [
        attempt for attempt in _store().list_attempts_for_user(user_id)
        if attempt.get("quiz_id") in quiz_ids and attempt.get("score") is not None
    ]

    best_scores: dict[int, float] = {}
    latest_activity = None
    for attempt in user_attempts:
        quiz_id = int(attempt["quiz_id"])
        score = float(attempt.get("score") or 0)
        best_scores[quiz_id] = max(best_scores.get(quiz_id, 0.0), score)
        created_at = attempt.get("created_at")
        if created_at and (latest_activity is None or created_at > latest_activity):
            latest_activity = created_at

    total_lessons = len(lessons)
    total_quizzes = len(quizzes)
    attempted_quizzes = len(best_scores)
    passed_quizzes = sum(1 for score in best_scores.values() if _quiz_passed(score))
    completion_percent = round((len(completed_lessons) / total_lessons) * 100, 1) if total_lessons else 0.0

    return {
        "course_id": course["id"],
        "completed_lessons": len(completed_lessons),
        "total_lessons": total_lessons,
        "completion_percent": completion_percent,
        "passed_quizzes": passed_quizzes,
        "total_quizzes": total_quizzes,
        "attempted_quizzes": attempted_quizzes,
        "last_activity_at": latest_activity.isoformat() if latest_activity else None,
    }


def _course_lesson_progress_payload(course_id: int, user_id: int) -> list[dict]:
    lessons = _store().list_lessons_for_course(course_id)
    completed_lessons = {
        item["lesson_id"]
        for item in _store().list_completed_lessons_for_user(user_id)
        if item.get("lesson_id") is not None
    }
    attempts = _store().list_attempts_for_user(user_id)
    attempts_by_quiz: dict[int, list[dict]] = {}
    for attempt in attempts:
        quiz_id = attempt.get("quiz_id")
        score = attempt.get("score")
        if quiz_id is None or score is None:
            continue
        attempts_by_quiz.setdefault(int(quiz_id), []).append(attempt)

    payload = []
    for lesson in lessons:
        quizzes = _store().list_quizzes_for_lesson(lesson["id"])
        quiz = quizzes[0] if quizzes else None
        lesson_payload = {
            "lesson_id": lesson["id"],
            "lesson_title": lesson["title"],
            "lesson_order": lesson["order"],
            "lesson_completed": lesson["id"] in completed_lessons,
            "quiz_available": bool(quiz),
            "quiz_attempted": False,
            "quiz_passed": False,
            "best_score": None,
            "attempt_count": 0,
            "latest_attempt_at": None,
        }
        if quiz:
            quiz_attempts = attempts_by_quiz.get(int(quiz["id"]), [])
            if quiz_attempts:
                lesson_payload["quiz_attempted"] = True
                lesson_payload["attempt_count"] = len(quiz_attempts)
                best_score = max(float(item.get("score") or 0) for item in quiz_attempts)
                latest_attempt = max(
                    (item.get("created_at") for item in quiz_attempts if item.get("created_at") is not None),
                    default=None,
                )
                lesson_payload["best_score"] = round(best_score, 2)
                lesson_payload["quiz_passed"] = _quiz_passed(best_score)
                lesson_payload["latest_attempt_at"] = latest_attempt.isoformat() if latest_attempt else None
        payload.append(lesson_payload)
    return payload


class LessonSchema(BaseModel):
    id: int
    title: str
    content: str
    order: int
    quiz_count: int
    has_quiz: bool
    estimated_minutes: int
    summary: str


class CourseSchema(BaseModel):
    id: int
    title: str
    description: str
    lesson_count: int
    lesson_ids: List[int]
    quiz_count: int
    difficulty: str
    estimated_effort: str


class CourseQuizSummarySchema(BaseModel):
    id: int
    title: str
    xp_reward: int
    question_count: int


class CourseLessonContentSchema(LessonSchema):
    quizzes: list[CourseQuizSummarySchema]


class CourseContentMapSchema(BaseModel):
    course: CourseSchema
    lessons: list[CourseLessonContentSchema]


@router.get("/", response_model=List[CourseSchema])
def get_courses(db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    courses = _store().list_courses()
    return [
        {
            "id": course["id"],
            "title": course["title"],
            "description": course["description"],
            **_course_metadata(course),
        }
        for course in courses
    ]


@router.get("/{course_id}/lessons", response_model=List[LessonSchema])
def get_lessons(course_id: int, db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    lessons = _store().list_lessons_for_course(course_id)
    if not lessons:
        return []
    return [_lesson_summary(lesson) for lesson in lessons]


@router.get("/{course_id}/content-map", response_model=CourseContentMapSchema)
def get_course_content_map(course_id: int, db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    course = _store().get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = _store().list_lessons_for_course(course_id)

    lesson_payloads = []
    for lesson in lessons:
        quizzes = _store().list_quizzes_for_lesson(lesson["id"])
        lesson_payloads.append(
            {
                **_lesson_summary(lesson),
                "quizzes": [
                    {
                        "id": quiz["id"],
                        "title": quiz["title"],
                        "xp_reward": quiz.get("xp_reward") or 100,
                        "question_count": _question_count(quiz),
                    }
                    for quiz in quizzes
                ],
            }
        )

    return {
        "course": {
            "id": course["id"],
            "title": course["title"],
            "description": course["description"],
            **_course_metadata(course),
        },
        "lessons": lesson_payloads,
    }


@router.get("/lessons/{lesson_id}", response_model=LessonSchema)
def get_lesson(lesson_id: int, db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    lesson = _store().get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return _lesson_summary(lesson)


@router.get("/progress/summary")
def get_current_user_course_progress(
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.get_active_user),
):
    _store().ensure_bootstrapped(db)
    return [
        _course_progress_payload(course, current_user.id)
        for course in _store().list_courses()
    ]


@router.get("/{course_id}/progress")
def get_course_progress(
    course_id: int,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.get_active_user),
):
    _store().ensure_bootstrapped(db)
    course = _store().get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {
        "course_id": course_id,
        "course_title": course["title"],
        "summary": _course_progress_payload(course, current_user.id),
        "lessons": _course_lesson_progress_payload(course_id, current_user.id),
    }
