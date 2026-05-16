from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import database, dependencies
import json
from datetime import datetime
from firestore_primary_store import get_store

router = APIRouter()


def _store():
    return get_store()


def _safe_name(user: dict | None) -> str:
    return _store().user_display_name(user)


def _valid_scored_attempts() -> list[dict]:
    return _store().list_valid_attempts("user_id", "quiz_id", "score")


def _course_summary(course: dict) -> dict:
    lesson_count = len(_store().list_lessons_for_course(course["id"]))
    return {
        "id": course["id"],
        "title": course["title"],
        "description": course["description"],
        "lesson_count": lesson_count,
    }


def _quiz_question_count(quiz: dict) -> int:
    try:
        questions = json.loads(quiz["questions"])
        return len(questions) if isinstance(questions, list) else 0
    except (TypeError, json.JSONDecodeError):
        return 0


def _quiz_summary(quiz: dict) -> dict:
    return {
        "id": quiz["id"],
        "lesson_id": quiz["lesson_id"],
        "title": quiz["title"],
        "xp_reward": quiz.get("xp_reward") or 100,
        "question_count": _quiz_question_count(quiz),
    }


def _assignment_summary(assignment: dict) -> dict:
    quiz = _store().get_quiz(assignment["quiz_id"])
    course = _store().get_course(assignment["course_id"])
    return {
        "id": assignment["id"],
        "quiz_id": assignment["quiz_id"],
        "quiz_title": quiz["title"] if quiz else None,
        "course_id": assignment["course_id"],
        "course_title": course["title"] if course else None,
        "title": assignment["title"],
        "instructions": assignment.get("instructions", ""),
        "due_at": assignment["due_at"].isoformat() if assignment.get("due_at") else None,
        "is_published": assignment.get("is_published", False),
        "created_at": assignment["created_at"].isoformat() if assignment.get("created_at") else None,
    }

@router.get("/dashboard")
def get_teacher_dashboard(db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_teacher)):
    _store().ensure_bootstrapped(db)
    total_students = len(_store().list_by_role("student"))
    attempts = _valid_scored_attempts()
    avg_score = float(sum(item["score"] for item in attempts) / len(attempts)) if attempts else 0.0
    total_attempts = len(attempts)

    return {
        "overview": {
            "total_students": total_students,
            "average_score": avg_score,
            "total_attempts": total_attempts
        }
    }

@router.get("/students-progress")
def get_students_progress(db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_teacher)):
    _store().ensure_bootstrapped(db)
    students = _store().list_by_role("student")
    
    result = []
    for s in students:
        profile = _store().get_profile_by_user_id(s["id"])
        completed = len(_store().list_completed_lessons_for_user(s["id"]))
        result.append({
            "id": s["id"],
            "name": _safe_name(s),
            "email": _store().user_email(s),
            "level": profile["level"] if profile else 1,
            "xp": profile["xp"] if profile else 0,
            "streak": profile["streak"] if profile else 0,
            "lessons_completed": completed,
            "completed_lessons": completed,
        })
    return result

@router.get("/recent-attempts")
def get_recent_attempts(limit: int = 10, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_teacher)):
    _store().ensure_bootstrapped(db)
    attempts = _valid_scored_attempts()[:limit]
    result = []
    for a in attempts:
        user = _store().get_user_by_id(a["user_id"])
        quiz = _store().get_quiz(a["quiz_id"])
        result.append({
            "id": a["id"],
            "user_name": _safe_name(user),
            "quiz_title": quiz["title"] if quiz else "Quiz",
            "score": a["score"],
            "earned_xp": a["earned_xp"],
            "created_at": a["created_at"].isoformat() if a.get("created_at") else None
        })
    return result

class CourseCreate(BaseModel):
    title: str
    description: str

class LessonCreate(BaseModel):
    course_id: int
    title: str
    content: str
    order: int

class QuizCreate(BaseModel):
    lesson_id: int
    title: str
    questions: list
    xp_reward: int = 100


class AssignmentCreate(BaseModel):
    quiz_id: int
    course_id: int
    title: str
    instructions: str = ""
    due_at: Optional[datetime] = None


class AssignmentUpdate(BaseModel):
    quiz_id: int
    course_id: int
    title: str
    instructions: str = ""
    due_at: Optional[datetime] = None

@router.post("/courses")
def create_course(course: CourseCreate, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_teacher)):
    _store().ensure_bootstrapped(db)
    new_course = _store().create_course(course.title, course.description, db=db)
    return _course_summary(new_course)

@router.post("/lessons")
def create_lesson(lesson: LessonCreate, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_teacher)):
    _store().ensure_bootstrapped(db)
    course = _store().get_course(lesson.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    new_lesson = _store().create_lesson(
        course_id=lesson.course_id,
        title=lesson.title,
        content=lesson.content,
        order=lesson.order,
        db=db,
    )
    return {
        "id": new_lesson["id"],
        "course_id": new_lesson["course_id"],
        "course_title": course["title"],
        "title": new_lesson["title"],
        "content": new_lesson["content"],
        "order": new_lesson["order"],
    }

@router.post("/quizzes")
def create_quiz(quiz: QuizCreate, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_teacher)):
    _store().ensure_bootstrapped(db)
    lesson = _store().get_lesson(quiz.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if not quiz.questions:
        raise HTTPException(status_code=400, detail="Quiz must contain at least one question")
    if quiz.xp_reward < 0 or quiz.xp_reward > 500:
        raise HTTPException(status_code=400, detail="XP reward must be between 0 and 500")

    target_quiz, updated_existing = _store().create_or_update_quiz(
        lesson_id=quiz.lesson_id,
        title=quiz.title,
        xp_reward=quiz.xp_reward,
        questions=json.dumps(quiz.questions),
        db=db,
    )
    return {
        **_quiz_summary(target_quiz),
        "lesson_title": lesson["title"],
        "updated_existing_quiz": updated_existing,
    }


@router.get("/assignments")
def get_assignments(
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.require_teacher),
):
    _store().ensure_bootstrapped(db)
    assignments = _store().list_assignments()
    return [_assignment_summary(assignment) for assignment in assignments]


@router.post("/assignments")
def create_assignment(
    assignment: AssignmentCreate,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.require_teacher),
):
    _store().ensure_bootstrapped(db)
    course = _store().get_course(assignment.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = _store().get_quiz(assignment.quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    new_assignment = _store().create_assignment(
        {
            "quiz_id": assignment.quiz_id,
            "course_id": assignment.course_id,
            "title": assignment.title,
            "instructions": assignment.instructions,
            "due_at": assignment.due_at,
        },
        db=db,
    )
    return _assignment_summary(new_assignment)


@router.put("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.require_teacher),
):
    _store().ensure_bootstrapped(db)
    assignment = _store().get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = _store().get_course(payload.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = _store().get_quiz(payload.quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    assignment = _store().update_assignment(
        assignment_id,
        {
            "quiz_id": payload.quiz_id,
            "course_id": payload.course_id,
            "title": payload.title,
            "instructions": payload.instructions,
            "due_at": payload.due_at,
        },
        db=db,
    )
    return _assignment_summary(assignment)


@router.put("/assignments/{assignment_id}/publish")
def publish_assignment(
    assignment_id: int,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.require_teacher),
):
    _store().ensure_bootstrapped(db)
    assignment = _store().get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment = _store().update_assignment(
        assignment_id,
        {"is_published": not assignment.get("is_published", False)},
        db=db,
    )
    return _assignment_summary(assignment)


@router.get("/analytics-summary")
def get_teacher_analytics_summary(
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.require_teacher),
):
    _store().ensure_bootstrapped(db)
    attempts = _valid_scored_attempts()
    lessons_count = len(_store().list_lessons())
    student_count = len(_store().list_by_role("student"))

    if attempts:
        average_score = float(sum(attempt["score"] for attempt in attempts) / len(attempts))
    else:
        average_score = 0.0

    quiz_scores: dict[int, list[float]] = {}
    for attempt in attempts:
        quiz_scores.setdefault(attempt["quiz_id"], []).append(attempt["score"])

    weak_topics = []
    for quiz_id, scores in quiz_scores.items():
        quiz = _store().get_quiz(quiz_id)
        if not quiz:
            continue
        avg = sum(scores) / len(scores)
        weak_topics.append({
            "quiz_id": quiz_id,
            "quiz_title": quiz["title"],
            "average_score": round(avg, 2),
        })
    weak_topics.sort(key=lambda item: item["average_score"])
    weak_topics = weak_topics[:3]

    completed_lessons = sum(
        len(_store().list_completed_lessons_for_user(student["id"]))
        for student in _store().list_by_role("student")
        if student.get("id") is not None
    )
    total_possible_completions = student_count * lessons_count
    recent_completion_rate = (
        round(completed_lessons / total_possible_completions, 2)
        if total_possible_completions
        else 0.0
    )

    students_needing_attention = []
    students = _store().list_by_role("student")
    for student in students:
        student_attempts = [attempt for attempt in attempts if attempt["user_id"] == student["id"]]
        if student_attempts:
            student_avg = sum(attempt["score"] for attempt in student_attempts) / len(student_attempts)
        else:
            student_avg = 0.0
        completed = len(_store().list_completed_lessons_for_user(student["id"]))
        if student_avg < 0.7 or completed == 0:
            students_needing_attention.append({
                "user_id": student["id"],
                "name": _safe_name(student),
                "average_score": round(student_avg, 2),
                "completed_lessons": completed,
            })

    return {
        "weak_topics": weak_topics,
        "recent_completion_rate": recent_completion_rate,
        "average_score": round(average_score, 2),
        "students_needing_attention": students_needing_attention,
    }

