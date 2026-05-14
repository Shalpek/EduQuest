import sys
from pathlib import Path
import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database  # noqa: E402
import models  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    testing_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=testing_engine,
    )

    database.engine = testing_engine
    database.SessionLocal = testing_session_local

    models.Base.metadata.drop_all(bind=testing_engine)
    models.Base.metadata.create_all(bind=testing_engine)

    seed = importlib.import_module("seed")
    seed.SessionLocal = testing_session_local
    seed.engine = testing_engine
    seed.seed_db()

    import main  # noqa: E402

    return TestClient(main.app)


@pytest.fixture()
def seeded_ids(client):
    return {
        "student@eduquest.com": 1,
        "alice@eduquest.com": 2,
        "bob@eduquest.com": 3,
        "teacher@eduquest.com": 4,
        "admin@eduquest.com": 5,
    }


@pytest.fixture()
def auth_headers(client):
    def _build(email: str, password: str = "password123"):
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200, response.text
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    return _build
