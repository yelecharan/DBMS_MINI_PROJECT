"""Authentication + role-based access control (API layer AND database layer)."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.db import pg_session


def test_login_success_returns_role(client):
    r = client.post("/api/auth/login", json={"username": "guard", "password": "Guard@123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "security"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401


def test_service_account_cannot_log_in(client):
    from app.config import settings
    r = client.post("/api/auth/login",
                    json={"username": settings.PG_APP_USER, "password": settings.PG_APP_PASSWORD})
    assert r.status_code == 401


def test_no_token_is_rejected(client):
    assert client.get("/api/employees").status_code == 401


def test_tampered_token_is_rejected(client):
    r = client.get("/api/employees", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401


def test_me(client, admin):
    assert client.get("/api/auth/me", headers=admin).json() == {"username": "admin", "role": "admin"}


@pytest.mark.parametrize("method,url", [
    ("post", "/api/gates"), ("delete", "/api/employees/1"), ("delete", "/api/incidents/1"),
    ("put", "/api/incidents/1"), ("delete", "/api/alerts/ALT-X"), ("post", "/api/alerts"),
    ("delete", "/api/observations/OBS-X"), ("delete", "/api/access-logs/1")])
def test_security_blocked_from_admin_endpoints(client, guard, method, url):
    r = getattr(client, method)(url, headers=guard, **({"json": {}} if method in ("post", "put") else {}))
    assert r.status_code == 403


def test_security_allowed_actions(client, guard):
    assert client.get("/api/access-logs", headers=guard).status_code == 200
    assert client.get("/api/incidents", headers=guard).status_code == 200
    r = client.patch("/api/incidents/9/status", headers=guard, json={"status": "INVESTIGATING"})
    assert r.status_code == 200
    client.patch("/api/incidents/9/status", headers=guard, json={"status": "OPEN"})


def test_database_enforces_security_role():
    """Even if the API check were bypassed, PostgreSQL refuses (SET LOCAL ROLE gs_security)."""
    with pytest.raises(ProgrammingError, match="permission denied"):
        with pg_session("security") as conn:
            conn.execute(text("DELETE FROM incidents WHERE incident_id = -1"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        with pg_session("security") as conn:
            conn.execute(text("UPDATE incidents SET severity = 'LOW' WHERE incident_id = -1"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        with pg_session("security") as conn:
            conn.execute(text("INSERT INTO gates(gate_name, location) VALUES ('x','y')"))


def test_database_column_level_privilege():
    with pg_session("security") as conn:     # UPDATE(status) is granted
        conn.execute(text("UPDATE incidents SET status = status WHERE incident_id = 1"))


def test_app_role_has_no_privileges_without_set_role():
    from app.db import engine
    with pytest.raises(ProgrammingError, match="permission denied"):
        with engine.connect() as conn:
            conn.execute(text("SELECT * FROM employees"))
