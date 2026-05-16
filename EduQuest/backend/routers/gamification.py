from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database
from pydantic import BaseModel
from typing import List
import dependencies
from firestore_primary_store import get_store

router = APIRouter()


def _store():
    return get_store()

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
    current_user = Depends(dependencies.get_active_user),
):
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to view this profile")

    _store().ensure_bootstrapped(db)
    profile = _store().get_profile_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    completed = _store().list_completed_lessons_for_user(user_id)
    completed_ids = [item["lesson_id"] for item in completed]

    return {
        "xp": profile["xp"],
        "level": profile["level"],
        "streak": profile["streak"],
        "completed_lessons": completed_ids,
    }

@router.post("/profile/{user_id}/complete_lesson/{lesson_id}")
def complete_lesson(
    user_id: int,
    lesson_id: int,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.get_active_user),
):
    if current_user.id != user_id and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    _store().ensure_bootstrapped(db)
    existing = _store().get_completed_lesson(user_id, lesson_id)
    if not existing:
        _store().create_completed_lesson(user_id, lesson_id, db=db)
        profile = _store().get_profile_by_user_id(user_id)
        if profile:
            new_xp = profile["xp"] + 10
            _store().update_profile(
                profile["id"],
                {
                    "xp": new_xp,
                    "level": (new_xp // 500) + 1,
                },
                db=db,
            )
    return {"status": "success"}
