from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, dependencies
from pydantic import BaseModel
import json
from datetime import datetime
from firestore_primary_store import get_store

router = APIRouter()


def _store():
    return get_store()

class QuizSchema(BaseModel):
    id: int
    title: str
    xp_reward: int
    questions: str

    class Config:
        from_attributes = True

class QuizSubmit(BaseModel):
    answers: list[int]

@router.get("/lesson/{lesson_id}", response_model=QuizSchema)
def get_quiz_by_lesson(lesson_id: int, db: Session = Depends(database.get_db), current_user=Depends(dependencies.get_active_user)):
    _store().ensure_bootstrapped(db)
    quiz = _store().get_quiz_by_lesson(lesson_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz

@router.post("/{quiz_id}/submit")
def submit_quiz(quiz_id: int, submission: QuizSubmit, db: Session = Depends(database.get_db), current_user=Depends(dependencies.get_active_user)):
    _store().ensure_bootstrapped(db)
    quiz = _store().get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    try:
        questions = json.loads(quiz["questions"])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Quiz questions are misconfigured") from exc

    total_questions = len(questions)
    if total_questions == 0:
        raise HTTPException(status_code=400, detail="Quiz has no questions")
    if len(submission.answers) != total_questions:
        raise HTTPException(status_code=400, detail="Answer count does not match quiz")

    correct_answers = 0
    wrong_answers = []
    wrong_answer_indexes: list[int] = []
    for index, (question, answer_index) in enumerate(zip(questions, submission.answers)):
        options = question.get("options", [])
        correct_index = question.get("answer")
        if not isinstance(answer_index, int) or answer_index < 0 or answer_index >= len(options):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid answer index for question {index + 1}",
            )

        if answer_index == correct_index:
            correct_answers += 1
            continue

        wrong_answer_indexes.append(index)
        wrong_answers.append(
            {
                "question": question.get("q", f"Question {index + 1}"),
                "options": options,
                "user_answer_index": answer_index,
                "correct_answer_index": correct_index,
            }
        )

    score = correct_answers / total_questions
    config = _store().get_system_config()
    retries_enabled = config["retries_enabled"] if config else True
    if not retries_enabled:
        existing_attempt = _store().find_attempt_by_user_quiz(current_user.id, quiz_id)
        if existing_attempt:
            raise HTTPException(
                status_code=409,
                detail="Quiz retries are disabled for this lesson",
            )

    base_xp = quiz.get("xp_reward") or (config["xp_per_quiz"] if config else 100)

    xp_earned = int(score * base_xp)
    profile = _store().get_profile_by_user_id(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    current_xp = profile["xp"] + xp_earned
    new_level = profile["level"]
    if current_xp > profile["level"] * 500:
        new_level = profile["level"] + 1
    attempt_payload = {
        "user_id": current_user.id,
        "quiz_id": quiz_id,
        "score": score,
        "earned_xp": xp_earned,
        "student_answers_json": json.dumps(submission.answers),
        "quiz_questions_snapshot_json": json.dumps(questions),
        "wrong_answer_indexes_json": json.dumps(wrong_answer_indexes),
        "created_at": datetime.utcnow(),
    }
    attempt, updated_profile = _store().create_attempt(
        payload=attempt_payload,
        profile_updates={
            "xp": current_xp,
            "streak": profile["streak"] + 1,
            "level": new_level,
        },
        db=db,
    )
    lesson_id = quiz.get("lesson_id")
    if lesson_id is not None and not _store().get_completed_lesson(current_user.id, int(lesson_id)):
        _store().create_completed_lesson(current_user.id, int(lesson_id), db=db)

    # Adaptive Feedback Mechanism
    feedback_message = "Keep practicing! You can try this again to master the content."
    if score == 1.0:
        feedback_message = "Perfect Score! You've completely mastered this lesson. Proceed to the next module!"
    elif score >= 0.7:
        feedback_message = "Great effort! You've grasped the core concepts. Review your mistakes to achieve perfection."
    
    return {
        "message": "Quiz submitted",
        "attempt_id": attempt["id"],
        "score": score,
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "xp_earned": xp_earned,
        "new_level": updated_profile["level"] if updated_profile else 1,
        "new_streak": updated_profile["streak"] if updated_profile else 0,
        "feedback_message": feedback_message,
        "wrong_answer_indexes": wrong_answer_indexes,
        "wrong_answers": wrong_answers,
    }


@router.get("/user/{user_id}/attempts")
def get_user_attempts(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.get_active_user),
):
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Not allowed to access another user's attempts")

    _store().ensure_bootstrapped(db)
    attempts = _store().list_attempts_for_user(user_id)
    result = []
    for a in attempts:
        quiz = _store().get_quiz(a["quiz_id"])
        result.append({
            "id": a["id"],
            "quiz_id": a["quiz_id"],
            "quiz_title": quiz["title"] if quiz else "Unknown",
            "score": a["score"],
            "earned_xp": a["earned_xp"],
            "created_at": a["created_at"].isoformat() if a.get("created_at") else None
        })
    return result
