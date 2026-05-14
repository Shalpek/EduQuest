from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, database, dependencies
from pydantic import BaseModel
import json

router = APIRouter()

class QuizSchema(BaseModel):
    id: int
    title: str
    questions: str

    class Config:
        from_attributes = True

class QuizSubmit(BaseModel):
    answers: list[int]

@router.get("/lesson/{lesson_id}", response_model=QuizSchema)
def get_quiz_by_lesson(lesson_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_active_user)):
    quiz = db.query(models.Quiz).filter(models.Quiz.lesson_id == lesson_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz

@router.post("/{quiz_id}/submit")
def submit_quiz(quiz_id: int, submission: QuizSubmit, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_active_user)):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    try:
        questions = json.loads(quiz.questions)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Quiz questions are misconfigured") from exc

    total_questions = len(questions)
    if total_questions == 0:
        raise HTTPException(status_code=400, detail="Quiz has no questions")
    if len(submission.answers) != total_questions:
        raise HTTPException(status_code=400, detail="Answer count does not match quiz")

    correct_answers = 0
    wrong_answers = []
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

        wrong_answers.append(
            {
                "question": question.get("q", f"Question {index + 1}"),
                "options": options,
                "user_answer_index": answer_index,
                "correct_answer_index": correct_index,
            }
        )

    score = correct_answers / total_questions
    config = db.query(models.SystemConfig).first()
    retries_enabled = config.retries_enabled if config else True
    if not retries_enabled:
        existing_attempt = (
            db.query(models.Attempt)
            .filter(
                models.Attempt.user_id == current_user.id,
                models.Attempt.quiz_id == quiz_id,
            )
            .first()
        )
        if existing_attempt:
            raise HTTPException(
                status_code=409,
                detail="Quiz retries are disabled for this lesson",
            )

    base_xp = config.xp_per_quiz if config else 100

    xp_earned = int(score * base_xp)
    attempt = models.Attempt(
        user_id=current_user.id,
        quiz_id=quiz_id,
        score=score,
        earned_xp=xp_earned
    )
    db.add(attempt)
    
    # 2. Update Gamification Profile
    profile = db.query(models.GamificationProfile).filter(models.GamificationProfile.user_id == current_user.id).first()
    if profile:
        profile.xp += xp_earned
        profile.streak += 1
        if profile.xp > profile.level * 500:
            profile.level += 1
            
    db.commit()
    db.refresh(attempt)

    # Adaptive Feedback Mechanism
    feedback_message = "Keep practicing! You can try this again to master the content."
    if score == 1.0:
        feedback_message = "Perfect Score! You've completely mastered this lesson. Proceed to the next module!"
    elif score >= 0.7:
        feedback_message = "Great effort! You've grasped the core concepts. Review your mistakes to achieve perfection."
    
    return {
        "message": "Quiz submitted",
        "attempt_id": attempt.id,
        "score": score,
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "xp_earned": xp_earned,
        "new_level": profile.level if profile else 1,
        "new_streak": profile.streak if profile else 0,
        "feedback_message": feedback_message,
        "wrong_answers": wrong_answers,
    }


@router.get("/user/{user_id}/attempts")
def get_user_attempts(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Not allowed to access another user's attempts")

    attempts = db.query(models.Attempt).filter(models.Attempt.user_id == user_id).order_by(models.Attempt.created_at.desc()).all()
    result = []
    for a in attempts:
        quiz = db.query(models.Quiz).filter(models.Quiz.id == a.quiz_id).first()
        result.append({
            "id": a.id,
            "quiz_id": a.quiz_id,
            "quiz_title": quiz.title if quiz else "Unknown",
            "score": a.score,
            "earned_xp": a.earned_xp,
            "created_at": a.created_at.isoformat() if a.created_at else None
        })
    return result
