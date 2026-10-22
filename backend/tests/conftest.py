import os

import pytest

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
if TEST_DATABASE_URL:
    database_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if "test" not in database_name and os.getenv("ALLOW_NON_TEST_DB_RESET") != "1":
        raise RuntimeError(
            "Refusing to run destructive tests against a database whose name "
            "does not contain 'test'. Set ALLOW_NON_TEST_DB_RESET=1 to override."
        )
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    os.environ["DATABASE_URL"] = "sqlite:///./test_vigil.db"

os.environ.setdefault("VIGIL_ENV", "test")
os.environ.setdefault("VIGIL_AUTO_SEED", "true")
os.environ.setdefault("VIGIL_SEED_ADMIN_PASSWORD", "TestAdminPassword123!")
os.environ.setdefault("VIGIL_SEED_DEMO_USERS", "true")
os.environ.setdefault("VIGIL_SEED_DEMO_PASSWORD", "TestNursePassword123!")
os.environ.setdefault("VIGIL_SEED_DEMO_PATIENTS", "true")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-deployment")

from fastapi.testclient import TestClient

from backend.event_store.database import Base, SessionLocal, engine
from backend.event_store.integrity import (
    assert_integrity_ready,
    ensure_chain_state,
    install_integrity_triggers,
)
from backend.main import app, seed_hospital_data


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_chain_state(db)
    finally:
        db.close()
    install_integrity_triggers(engine)
    seed_hospital_data()
    assert_integrity_ready(engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def nurse_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"staff_id": "NURSE_101", "password": "TestNursePassword123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"staff_id": "ADMIN_01", "password": "TestAdminPassword123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
