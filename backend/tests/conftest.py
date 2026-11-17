"""Shared fixtures. Tests talk to the REAL local PostgreSQL + MongoDB servers.
Run `python -m scripts.init_db` once before the tests (it loads the sample data).
Every test cleans up the rows/documents it creates."""
import sys
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402
from app.db import mongo_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _login(client, user, pwd):
    r = client.post("/api/auth/login", json={"username": user, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, settings.DEMO_ADMIN_USER, settings.DEMO_ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def guard(client):
    return _login(client, settings.DEMO_SECURITY_USER, settings.DEMO_SECURITY_PASSWORD)


@pytest.fixture()
def su():
    """Superuser connection inside a transaction that is always rolled back."""
    conn = psycopg.connect(host=settings.PG_HOST, port=settings.PG_PORT,
                           dbname=settings.PG_DATABASE, user=settings.PG_SUPERUSER,
                           password=settings.PG_SUPERUSER_PASSWORD)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture(scope="session")
def mdb():
    return mongo_db
