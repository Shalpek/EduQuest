from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
import models, database, dependencies
import json
from datetime import datetime

router = APIRouter()


def _course_summary(course: models.Course) -> dict:
    lesson_count = len(course.lessons) if course.lessons else 0
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "lesson_count": lesson_count,
    }


def _quiz_question_count(quiz: models.Quiz) -> int:
    try:
        questions = json.loads(quiz.questions)
        return len(questions) if isinstance(questions, list) else 0
    except (TypeError, json.JSONDecodeError):
        return 0


def _quiz_summary(quiz: models.Quiz) -> dict:
    return {
        "id": quiz.id,
        "lesson_id": quiz.lesson_id,
        "title": quiz.title,
        "question_count": _quiz_question_count(quiz),
    }


def _assignment_summary(assignment: models.Assignment) -> dict:
    quiz = assignment.quiz
    course = assignment.course
    return {
        "id": assignment.id,
        "quiz_id": assignment.quiz_id,
        "quiz_title": quiz.title if quiz else None,
        "course_id": assignment.course_id,
        "course_title": course.title if course else None,
        "title": assignment.title,
        "instructions": assignment.instructions,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "is_published": assignment.is_published,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
    }

@router.get("/dashboard")
def get_teacher_dashboard(db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_teacher)):
    # Total students
    total_students = db.query(models.User).filter(models.User.role == "student").count()
    
    # Average score & Total Attempts
    attempts_query = db.query(func.avg(models.Attempt.score), func.count(models.Attempt.id)).first()
    avg_score = float(attempts_query[0]) if attempts_query[0] is not None else 0.0
    total_attempts = int(attempts_query[1]) if attempts_query[1] is not None else 0

    return {
        "overview": {
            "total_students": total_students,
            "average_score": avg_score,
            "total_attempts": total_attempts
        }
    }

@router.get("/students-progress")
def get_students_progress(db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_teacher)):
    students = db.query(models.User).filter(models.User.role == "student").all()
    
    result = []
    for s in students:
        profile = s.profile
        completed = db.query(func.count(models.CompletedLesson.id)).filter(models.CompletedLesson.user_id == s.id).scalar()
        result.append({
            "id": s.id,
            "name": s.full_name,
            "email": s.email,
            "level": profile.level if profile else 1,
            "xp": profile.xp if profile else 0,
            "streak": profile.streak if profile else 0,
            "lessons_completed": completed
        })
    return result

@router.get("/recent-attempts")
def get_recent_attempts(limit: int = 10, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_teacher)):
    attempts = db.query(models.Attempt).order_by(models.Attempt.created_at.desc()).limit(limit).all()
    result = []
    for a in attempts:
        user = db.query(models.User).filter(models.User.id == a.user_id).first()
        quiz = db.query(models.Quiz).filter(models.Quiz.id == a.quiz_id).first()
        result.append({
            "id": a.id,
            "user_name": user.full_name if user else "Unknown",
            "quiz_title": quiz.title if quiz else "Quiz",
            "score": a.score,
            "earned_xp": a.earned_xp,
            "created_at": a.created_at.isoformat() if a.created_at else None
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
def create_course(course: CourseCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_teacher)):
    new_course = models.Course(title=course.title, description=course.description)
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    return _course_summary(new_course)

@router.post("/lessons")
def create_lesson(lesson: LessonCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_teacher)):
    course = db.query(models.Course).filter(models.Course.id == lesson.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    new_lesson = models.Lesson(course_id=lesson.course_id, title=lesson.title, content=lesson.content, order=lesson.order)
    db.add(new_lesson)
    db.commit()
    db.refresh(new_lesson)
    return {
        "id": new_lesson.id,
        "course_id": new_lesson.course_id,
        "course_title": course.title,
        "title": new_lesson.title,
        "content": new_lesson.content,
        "order": new_lesson.order,
    }

@router.post("/quizzes")
def create_quiz(quiz: QuizCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_teacher)):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == quiz.lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    new_quiz = models.Quiz(lesson_id=quiz.lesson_id, title=quiz.title, questions=json.dumps(quiz.questions))
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    return {
        **_quiz_summary(new_quiz),
        "lesson_title": lesson.title,
    }


@router.get("/assignments")
def get_assignments(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.require_teacher),
):
    assignments = db.query(models.Assignment).order_by(models.Assignment.created_at.desc()).all()
    return [_assignment_summary(assignment) for assignment in assignments]


@router.post("/assignments")
def create_assignment(
    assignment: AssignmentCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.require_teacher),
):
    course = db.query(models.Course).filter(models.Course.id == assignment.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == assignment.quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    new_assignment = models.Assignment(
        quiz_id=assignment.quiz_id,
        course_id=assignment.course_id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return _assignment_summary(new_assignment)


@router.put("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.require_teacher),
):
    assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = db.query(models.Course).filter(models.Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == payload.quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    assignment.quiz_id = payload.quiz_id
    assignment.course_id = payload.course_id
    assignment.title = payload.title
    assignment.instructions = payload.instructions
    assignment.due_at = payload.due_at
    db.commit()
    db.refresh(assignment)
    return _assignment_summary(assignment)


@router.put("/assignments/{assignment_id}/publish")
def publish_assignment(
    assignment_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.require_teacher),
):
    assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment.is_published = not assignment.is_published
    db.commit()
    db.refresh(assignment)
    return _assignment_summary(assignment)


@router.get("/analytics-summary")
def get_teacher_analytics_summary(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.require_teacher),
):
    attempts = db.query(models.Attempt).all()
    lessons_count = db.query(models.Lesson).count()
    student_count = db.query(models.User).filter(models.User.role == "student").count()

    if attempts:
        average_score = float(sum(attempt.score for attempt in attempts) / len(attempts))
    else:
        average_score = 0.0

    quiz_scores: dict[int, list[float]] = {}
    for attempt in attempts:
        quiz_scores.setdefault(attempt.quiz_id, []).append(attempt.score)

    weak_topics = []
    for quiz_id, scores in quiz_scores.items():
        quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
        if not quiz:
            continue
        avg = sum(scores) / len(scores)
        weak_topics.append({
            "quiz_id": quiz_id,
            "quiz_title": quiz.title,
            "average_score": round(avg, 2),
        })
    weak_topics.sort(key=lambda item: item["average_score"])
    weak_topics = weak_topics[:3]

    completed_lessons = db.query(models.CompletedLesson).count()
    total_possible_completions = student_count * lessons_count
    recent_completion_rate = (
        round(completed_lessons / total_possible_completions, 2)
        if total_possible_completions
        else 0.0
    )

    students_needing_attention = []
    students = db.query(models.User).filter(models.User.role == "student").all()
    for student in students:
        student_attempts = [attempt for attempt in attempts if attempt.user_id == student.id]
        if student_attempts:
            student_avg = sum(attempt.score for attempt in student_attempts) / len(student_attempts)
        else:
            student_avg = 0.0
        completed = db.query(func.count(models.CompletedLesson.id)).filter(models.CompletedLesson.user_id == student.id).scalar() or 0
        if student_avg < 0.7 or completed == 0:
            students_needing_attention.append({
                "user_id": student.id,
                "name": student.full_name,
                "average_score": round(student_avg, 2),
                "completed_lessons": completed,
            })

    return {
        "weak_topics": weak_topics,
        "recent_completion_rate": recent_completion_rate,
        "average_score": round(average_score, 2),
        "students_needing_attention": students_needing_attention,
    }

