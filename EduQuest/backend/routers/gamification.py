from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, database
from pydantic import BaseModel
from typing import List
import dependencies

router = APIRouter()

class ProfileSchema(BaseModel):
    xp: int
    level: int
    streak: int
    completed_lessons: List[int] = []
    
    class Config:
        from_attributes = True

@router.get("/profile/{user_id}", response_model=ProfileSchema)
def get_gamification_profile(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to view this profile")

    profile = db.query(models.GamificationProfile).filter(models.GamificationProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    completed = db.query(models.CompletedLesson).filter(models.CompletedLesson.user_id == user_id).all()
    completed_ids = [c.lesson_id for c in completed]

    return {"xp": profile.xp, "level": profile.level, "streak": profile.streak, "completed_lessons": completed_ids}

@router.post("/profile/{user_id}/complete_lesson/{lesson_id}")
def complete_lesson(
    user_id: int,
    lesson_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    existing = db.query(models.CompletedLesson).filter(
        models.CompletedLesson.user_id == user_id, 
        models.CompletedLesson.lesson_id == lesson_id
    ).first()
    if not existing:
        new_completion = models.CompletedLesson(user_id=user_id, lesson_id=lesson_id)
        db.add(new_completion)
        
        # Award some XP for completing a lesson
        profile = db.query(models.GamificationProfile).filter(models.GamificationProfile.user_id == user_id).first()
        if profile:
            profile.xp += 10
            # Simple level up logic
            profile.level = (profile.xp // 500) + 1
            
        db.commit()
    return {"status": "success"}
