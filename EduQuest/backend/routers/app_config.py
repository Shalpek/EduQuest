from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import database
from firestore_primary_store import get_store


router = APIRouter()


def _store():
    return get_store()


class AppConfigResponse(BaseModel):
    ai_safety: bool
    retries_enabled: bool
    xp_per_quiz: int


@router.get("/config", response_model=AppConfigResponse)
def get_app_config(db: Session = Depends(database.get_db)):
    _store().ensure_bootstrapped(db)
    config = _store().get_system_config()
    if not config:
        return AppConfigResponse(
            ai_safety=True,
            retries_enabled=True,
            xp_per_quiz=100,
        )
    return AppConfigResponse(
        ai_safety=config["ai_safety"],
        retries_enabled=config["retries_enabled"],
        xp_per_quiz=config["xp_per_quiz"],
    )
