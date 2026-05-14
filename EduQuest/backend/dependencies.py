from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from database import get_db
import models
import auth_session


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token missing")
    try:
        payload = auth_session.verify_session_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return payload["sub"]


def get_active_user(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user

def require_teacher(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user

def require_admin(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user

def get_active_student(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_active_user(user_id=user_id, db=db)
