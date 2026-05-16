from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, database, dependencies
from pydantic import BaseModel, ConfigDict
import auth_session
from firestore_primary_store import as_record, get_store

router = APIRouter()


def _store():
    return get_store()

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


class RegisterProfilePayload(BaseModel):
    full_name: str


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    db_user = _store().get_user_by_email(user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = _store().create_user(
        email=user.email,
        full_name=user.full_name,
        hashed_password=f"mock_hash_{user.password}",
        db=db,
    )
    return {"id": new_user["id"], "email": new_user["email"], "message": "Registered successfully"}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    db_user = _store().get_user_by_email(user.email)
    if not db_user or db_user["hashed_password"] != f"mock_hash_{user.password}":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not db_user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    token = auth_session.create_session_token(db_user["id"], db_user["role"])
    return {
        "token": token,
        "token_type": "bearer",
        "user_id": db_user["id"],
        "role": db_user["role"],
        "email": db_user["email"],
        "full_name": db_user["full_name"],
    }


@router.post("/register-profile", response_model=CurrentUserResponse)
def register_profile(
    payload: RegisterProfilePayload,
    firebase_identity = Depends(dependencies.require_firebase_identity),
    db: Session = Depends(database.get_db),
):
    user = dependencies.provision_user_from_firebase_identity(
        db=db,
        firebase_identity=firebase_identity,
        full_name=payload.full_name,
    )
    return user


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: models.User = Depends(dependencies.get_active_user)):
    return current_user


@router.put("/me", response_model=CurrentUserResponse)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    updated = _store().update_user(
        current_user.id,
        {"full_name": payload.full_name.strip()},
        db=db,
    )
    return as_record(updated)


@router.put("/change-password")
def change_password(
    payload: PasswordUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if current_user.hashed_password != f"mock_hash_{payload.current_password}":
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    _store().update_user(
        current_user.id,
        {"hashed_password": f"mock_hash_{payload.new_password}"},
        db=db,
    )
    return {"message": "Password updated successfully"}
