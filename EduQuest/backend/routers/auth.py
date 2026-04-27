from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, database, dependencies
from pydantic import BaseModel, ConfigDict

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: str
    password: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool


class ProfileUpdate(BaseModel):
    full_name: str


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Simple mock password "hashing" for MVP
    new_user = models.User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=f"mock_hash_{user.password}"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # create default gamification profile
    profile = models.GamificationProfile(user_id=new_user.id)
    db.add(profile)
    db.commit()
    
    return {"id": new_user.id, "email": new_user.email, "message": "Registered successfully"}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or db_user.hashed_password != f"mock_hash_{user.password}":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return {
        "token": f"mock_token_{db_user.id}",
        "user_id": db_user.id,
        "role": db_user.role,
        "email": db_user.email,
        "full_name": db_user.full_name,
    }


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: models.User = Depends(dependencies.get_active_user)):
    return current_user


@router.put("/me", response_model=CurrentUserResponse)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    current_user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/change-password")
def change_password(
    payload: PasswordUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if current_user.hashed_password != f"mock_hash_{payload.current_password}":
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = f"mock_hash_{payload.new_password}"
    db.commit()
    return {"message": "Password updated successfully"}
