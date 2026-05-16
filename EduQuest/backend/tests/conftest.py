import sys
from pathlib import Path
import importlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database  # noqa: E402
import models  # noqa: E402
from firestore_primary_store import reset_store_for_tests  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    firestore_path = tmp_path / "firestore-local.json"
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
    os.environ["EDUQUEST_LOCAL_FIRESTORE_PATH"] = str(firestore_path)
    reset_store_for_tests()

    for module_name in list(sys.modules):
        if module_name == "main":
            sys.modules.pop(module_name, None)

    models.Base.metadata.drop_all(bind=testing_engine)
    models.Base.metadata.create_all(bind=testing_engine)

    seed = importlib.import_module("seed")
    seed.SessionLocal = testing_session_local
    seed.engine = testing_engine
    seed.seed_db(reset=True)

    if "main" in sys.modules:
        main = importlib.reload(sys.modules["main"])
    else:
        import main  # noqa: E402

    test_client = TestClient(main.app)
    try:
        yield test_client
    finally:
        os.environ.pop("EDUQUEST_LOCAL_FIRESTORE_PATH", None)


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
