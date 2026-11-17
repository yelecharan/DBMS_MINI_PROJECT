"""Third role: 'viewer' - a limited, read-only user (gs_viewer)."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.config import settings
from app.db import pg_session


@pytest.fixture(scope="module")
def viewer(client):
    r = client.post("/api/auth/login", json={"username": settings.DEMO_VIEWER_USER,
                                             "password": settings.DEMO_VIEWER_PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "viewer"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.parametrize("url", ["/api/dashboard", "/api/employees", "/api/cards", "/api/gates",
                                 "/api/access-logs", "/api/incidents", "/api/incidents/7",
                                 "/api/observations", "/api/reports", "/api/alerts",
                                 "/api/analytics/sql/join_incident_details",
                                 "/api/analytics/mongo/excess_per_gate"])
def test_viewer_can_read(client, viewer, url):
    assert client.get(url, headers=viewer).status_code == 200


def test_viewer_cannot_see_phone_numbers(client, viewer, admin):
    rows = client.get("/api/employees", headers=viewer).json()
    assert rows and all(r["phone"] is None for r in rows)
    assert client.get("/api/employees", headers=admin).json()[0]["phone"]


@pytest.mark.parametrize("method,url,body", [
    ("post", "/api/access-logs", {"card_no": "GS-1001", "gate_id": 1}),
    ("post", "/api/incidents/report-tailgating", {"scan_id": 30, "observed_count": 4}),
    ("patch", "/api/incidents/9/status", {"status": "RESOLVED"}),
    ("post", "/api/observations", {"incident_id": 1, "observed_count": 3, "authorized_count": 1}),
    ("post", "/api/reports", {"incident_id": 1, "description": "viewer should not write this"}),
    ("patch", "/api/alerts/ALT-X/ack", {}),
    ("post", "/api/gates", {"gate_name": "X gate", "location": "Y"}),
    ("delete", "/api/incidents/1", None),
])
def test_viewer_cannot_write(client, viewer, method, url, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(url, headers=viewer, **kwargs).status_code == 403


def test_database_enforces_viewer_limits():
    with pytest.raises(ProgrammingError, match="permission denied"):
        with pg_session("viewer") as conn:
            conn.execute(text("SELECT phone FROM employees"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        with pg_session("viewer") as conn:
            conn.execute(text("INSERT INTO access_logs(card_id, gate_id) VALUES (1, 1)"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        with pg_session("viewer") as conn:
            conn.execute(text("UPDATE incidents SET status = status WHERE incident_id = 1"))
    with pg_session("viewer") as conn:                     # allowed columns work
        assert conn.execute(text("SELECT COUNT(name) FROM employees")).scalar_one() >= 10
