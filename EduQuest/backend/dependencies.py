from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
import models

def get_current_user_id(x_user_id: int = Header(None)):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id header missing")
    return x_user_id


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
