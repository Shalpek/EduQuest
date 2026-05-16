from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import database
from firestore_primary_store import get_store

router = APIRouter()


def _store():
    return get_store()

@router.get("/overview")
def get_analytics(db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    total_users = len(_store().list_users())
    attempts = _store().list_valid_attempts("quiz_id", "score")
    total_attempts = len(attempts)
    
    avg_score = float(sum(item["score"] for item in attempts) / len(attempts)) if attempts else 0.0
    
    profiles = [
        _store().get_profile_by_user_id(user["id"])
        for user in _store().list_users()
        if user.get("id") is not None
    ]
    profiles = [profile for profile in profiles if profile]
    top_user = max(profiles, key=lambda item: item["xp"], default=None)
    
    attempts_by_course = []
    for course in _store().list_courses():
        lesson_ids = [lesson["id"] for lesson in _store().list_lessons_for_course(course["id"])]
        quiz_ids = {quiz["id"] for lesson_id in lesson_ids for quiz in _store().list_quizzes_for_lesson(lesson_id)}
        attempts_by_course.append(
            {
                "course": course["title"],
                "attempts": sum(1 for attempt in attempts if attempt.get("quiz_id") in quiz_ids),
            }
        )

    quiz_completion_stats = []
    for quiz in _store().list_quizzes():
        quiz_completion_stats.append(
            {
                "quiz": quiz["title"],
                "completions": sum(1 for attempt in attempts if attempt.get("quiz_id") == quiz["id"]),
            }
        )

    return {
        "total_users": total_users,
        "total_attempts": total_attempts,
        "average_score": avg_score,
        "top_xp": top_user["xp"] if top_user else 0,
        "attempts_by_course": attempts_by_course,
        "quiz_completion_stats": quiz_completion_stats
    }

