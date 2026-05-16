from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from database import get_db
import models
import auth_session
from firebase_auth_provider import (
    FirebaseConfigurationError,
    FirebaseIdentity,
    FirebaseVerificationError,
    verify_firebase_bearer_token,
)
from firestore_primary_store import as_record, get_store


bearer_scheme = HTTPBearer(auto_error=False)


def _store():
    return get_store()


def _link_firebase_uid(
    db: Session,
    user,
    firebase_identity: FirebaseIdentity,
):
    if getattr(user, "firebase_uid", None) != firebase_identity.uid:
        updated = _store().update_user(
            user.id,
            {"firebase_uid": firebase_identity.uid},
            db=db,
        )
        return as_record(updated)
    return user


def find_user_by_firebase_identity(
    db: Session,
    firebase_identity: FirebaseIdentity,
) -> object | None:
    user = None
    if firebase_identity.uid:
        user = as_record(_store().get_user_by_firebase_uid(firebase_identity.uid))
    if user:
        return user

    user = as_record(_store().get_user_by_email(firebase_identity.email))
    if user:
        return _link_firebase_uid(db, user, firebase_identity)
    return None


def provision_user_from_firebase_identity(
    db: Session,
    firebase_identity: FirebaseIdentity,
    full_name: str | None = None,
):
    user = find_user_by_firebase_identity(db, firebase_identity)
    preferred_name = (
        (full_name or "").strip()
        or firebase_identity.full_name
        or firebase_identity.email.split("@", 1)[0]
    )

    if user:
        changed = False
        updates = {}
        if preferred_name and user.full_name != preferred_name:
            updates["full_name"] = preferred_name
            changed = True
        if changed:
            updated = _store().update_user(user.id, updates, db=db)
            return as_record(updated)
        return user

    created = _store().create_user(
        email=firebase_identity.email,
        firebase_uid=firebase_identity.uid,
        full_name=preferred_name,
        hashed_password="firebase_auth_only",
        role="student",
        db=db,
    )
    return as_record(created)


def require_firebase_identity(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> FirebaseIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token missing")
    try:
        return verify_firebase_bearer_token(credentials.credentials)
    except FirebaseConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FirebaseVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def get_active_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token missing")
    _store().ensure_bootstrapped(db)

    user = None
    try:
        payload = auth_session.verify_session_token(credentials.credentials)
        user = as_record(_store().get_user_by_id(int(payload["sub"])))
    except ValueError:
        try:
            firebase_identity = verify_firebase_bearer_token(credentials.credentials)
        except FirebaseConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FirebaseVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        user = find_user_by_firebase_identity(db, firebase_identity)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user


def get_current_user_id(
    current_user: models.User = Depends(get_active_user),
):
    return current_user.id

def require_teacher(user=Depends(get_active_user)):
    if not user or user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user

def require_admin(user=Depends(get_active_user)):
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user

def get_active_student(user=Depends(get_active_user)):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    return user
