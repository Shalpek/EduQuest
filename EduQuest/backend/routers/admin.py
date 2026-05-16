from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import database, dependencies
from firestore_primary_store import get_store

router = APIRouter()


def _store():
    return get_store()


def _user_governance_summary(user: dict) -> dict:
    profile = _store().get_profile_by_user_id(user["id"])
    return {
        "id": user["id"],
        "email": _store().user_email(user),
        "name": _store().user_display_name(user),
        "role": user.get("role", "student"),
        "is_active": user.get("is_active", True),
        "xp": profile["xp"] if profile else 0,
        "level": profile["level"] if profile else 1,
        "streak": profile["streak"] if profile else 0,
    }

@router.get("/users")
def get_users(db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_admin)):
    _store().ensure_bootstrapped(db)
    users = _store().list_users()
    return [_user_governance_summary(user) for user in users]

@router.put("/users/{user_id}/status")
def toggle_user_status(user_id: int, active: bool, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_admin)):
    _store().ensure_bootstrapped(db)
    usr = _store().get_user_by_id(user_id)
    if not usr:
        raise HTTPException(status_code=404, detail="User not found")
    usr = _store().update_user(user_id, {"is_active": active}, db=db)
    return {"status": "success", "user": _user_governance_summary(usr)}

@router.put("/users/{user_id}/role")
def change_user_role(user_id: int, role: str, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_admin)):
    _store().ensure_bootstrapped(db)
    usr = _store().get_user_by_id(user_id)
    if not usr:
        raise HTTPException(status_code=404, detail="User not found")
    if role not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    usr = _store().update_user(user_id, {"role": role}, db=db)
    return {"status": "success", "user": _user_governance_summary(usr)}

class SystemConfigUpdate(BaseModel):
    ai_safety: bool
    retries_enabled: bool
    xp_per_quiz: int

@router.get("/config")
def get_system_config(db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_admin)):
    _store().ensure_bootstrapped(db)
    config = _store().get_system_config()
    if not config:
        return {"ai_safety": True, "retries_enabled": True, "xp_per_quiz": 100}
    return {
        "ai_safety": config["ai_safety"],
        "retries_enabled": config["retries_enabled"],
        "xp_per_quiz": config["xp_per_quiz"]
    }

@router.put("/config")
def update_system_config(cfg: SystemConfigUpdate, db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_admin)):
    _store().ensure_bootstrapped(db)
    _store().upsert_system_config(
        {
            "ai_safety": cfg.ai_safety,
            "retries_enabled": cfg.retries_enabled,
            "xp_per_quiz": cfg.xp_per_quiz,
        },
        db=db,
    )
    return {"status": "success"}

@router.get("/platform-status")
def get_platform_status(db: Session = Depends(database.get_db), current_user=Depends(dependencies.require_admin)):
    _store().ensure_bootstrapped(db)
    user_count = len(_store().list_users())
    course_count = len(_store().list_courses())
    lesson_count = len(_store().list_lessons())
    quiz_count = len(_store().list_quizzes())
    attempt_count = len(_store().list_attempts())

    config = _store().get_system_config()
    ai_safe_status = "Active" if (config and config["ai_safety"]) else "Disabled"
    users = _store().list_users()
    role_distribution = {"student": 0, "teacher": 0, "admin": 0}
    active_vs_inactive = {"active": 0, "inactive": 0}
    for user in users:
        role = user.get("role")
        if role in role_distribution:
            role_distribution[role] += 1
        if user.get("is_active", True):
            active_vs_inactive["active"] += 1
        else:
            active_vs_inactive["inactive"] += 1

    recent_ai_activity_count = len(_store().list_ai_logs())

    return {
        "services": {
            "tutor_api": "Online",
            "safety_filter": ai_safe_status,
            "database": "Firestore primary / SQLite backup"
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
            "ai_safety": config["ai_safety"] if config else True,
            "retries_enabled": config["retries_enabled"] if config else True,
            "xp_per_quiz": config["xp_per_quiz"] if config else 100,
        },
        "recent_ai_activity_count": recent_ai_activity_count,
    }


@router.get("/storage-consistency")
def get_storage_consistency(
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.require_admin),
):
    _store().ensure_bootstrapped(db)
    return _store().consistency_report(db)

