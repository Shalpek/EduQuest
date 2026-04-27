from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models, database, dependencies

router = APIRouter()


def _user_governance_summary(user: models.User) -> dict:
    profile = user.profile
    return {
        "id": user.id,
        "email": user.email,
        "name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "xp": profile.xp if profile else 0,
        "level": profile.level if profile else 1,
        "streak": profile.streak if profile else 0,
    }

@router.get("/users")
def get_users(db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_admin)):
    users = db.query(models.User).all()
    return [_user_governance_summary(user) for user in users]

@router.put("/users/{user_id}/status")
def toggle_user_status(user_id: int, active: bool, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_admin)):
    usr = db.query(models.User).filter(models.User.id == user_id).first()
    if not usr:
        raise HTTPException(status_code=404, detail="User not found")
    usr.is_active = active
    db.commit()
    db.refresh(usr)
    return {"status": "success", "user": _user_governance_summary(usr)}

@router.put("/users/{user_id}/role")
def change_user_role(user_id: int, role: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_admin)):
    usr = db.query(models.User).filter(models.User.id == user_id).first()
    if not usr:
        raise HTTPException(status_code=404, detail="User not found")
    if role not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    usr.role = role
    db.commit()
    db.refresh(usr)
    return {"status": "success", "user": _user_governance_summary(usr)}

class SystemConfigUpdate(BaseModel):
    ai_safety: bool
    retries_enabled: bool
    xp_per_quiz: int

@router.get("/config")
def get_system_config(db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_admin)):
    config = db.query(models.SystemConfig).first()
    if not config:
        return {"ai_safety": True, "retries_enabled": True, "xp_per_quiz": 100}
    return {
        "ai_safety": config.ai_safety,
        "retries_enabled": config.retries_enabled,
        "xp_per_quiz": config.xp_per_quiz
    }

@router.put("/config")
def update_system_config(cfg: SystemConfigUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_admin)):
    config = db.query(models.SystemConfig).first()
    if not config:
        config = models.SystemConfig()
        db.add(config)
    config.ai_safety = cfg.ai_safety
    config.retries_enabled = cfg.retries_enabled
    config.xp_per_quiz = cfg.xp_per_quiz
    db.commit()
    return {"status": "success"}

@router.get("/platform-status")
def get_platform_status(db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.require_admin)):
    # Count resources
    user_count = db.query(models.User).count()
    course_count = db.query(models.Course).count()
    lesson_count = db.query(models.Lesson).count()
    quiz_count = db.query(models.Quiz).count()
    attempt_count = db.query(models.Attempt).count()

    config = db.query(models.SystemConfig).first()
    ai_safe_status = "Active" if (config and config.ai_safety) else "Disabled"
    users = db.query(models.User).all()
    role_distribution = {"student": 0, "teacher": 0, "admin": 0}
    active_vs_inactive = {"active": 0, "inactive": 0}
    for user in users:
        if user.role in role_distribution:
            role_distribution[user.role] += 1
        if user.is_active:
            active_vs_inactive["active"] += 1
        else:
            active_vs_inactive["inactive"] += 1

    recent_ai_activity_count = db.query(models.AILog).count()

    return {
        "services": {
            "tutor_api": "Online Mock",
            "safety_filter": ai_safe_status,
            "database": "Connected"
        },
        "metrics": {
            "users": user_count,
            "courses": course_count,
            "lessons": lesson_count,
            "quizzes": quiz_count,
            "attempts": attempt_count
        },
        "role_distribution": role_distribution,
        "active_vs_inactive_users": active_vs_inactive,
        "config_snapshot": {
            "ai_safety": config.ai_safety if config else True,
            "retries_enabled": config.retries_enabled if config else True,
            "xp_per_quiz": config.xp_per_quiz if config else 100,
        },
        "recent_ai_activity_count": recent_ai_activity_count,
    }

