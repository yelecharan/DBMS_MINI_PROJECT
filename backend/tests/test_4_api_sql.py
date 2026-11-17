"""SQL CRUD through the API + JOIN / nested / recursive queries."""
from datetime import date, timedelta

import pytest

from app.routers.analytics import SQL_QUERIES


def test_employee_crud(client, admin):
    exp = str(date.today() + timedelta(days=365))
    r = client.post("/api/employees", headers=admin, json={
        "name": "Api Test", "department": "QA", "phone": "9111111111",
        "card_no": "gs-api1", "expiry_date": exp})
    assert r.status_code == 201, r.text
    emp_id = r.json()["emp_id"]
    try:
        lst = client.get("/api/employees", headers=admin, params={"search": "Api Test"}).json()
        assert lst[0]["card_numbers"] == "GS-API1" and lst[0]["card_count"] == 1
        r = client.put(f"/api/employees/{emp_id}", headers=admin,
                       json={"name": "Api Tested", "department": "QA", "phone": "9111111112"})
        assert r.status_code == 200 and r.json()["name"] == "Api Tested"
        assert client.post(f"/api/employees/{emp_id}/deactivate-cards",
                           headers=admin).json() == {"deactivated": 1}
    finally:
        assert client.delete(f"/api/employees/{emp_id}", headers=admin).status_code == 200
    assert client.get("/api/employees", headers=admin, params={"search": "Api Test"}).json() == []


def test_employee_validation(client, admin):
    r = client.post("/api/employees", headers=admin, json={
        "name": "X", "department": "QA", "phone": "abc", "card_no": "GS", "expiry_date": "2020-01-01"})
    assert r.status_code == 422


def test_gate_and_card_crud(client, admin):
    g = client.post("/api/gates", headers=admin, json={
        "gate_name": "Test Gate", "location": "Lab", "type": "EXIT", "status": "ACTIVE"})
    assert g.status_code == 201, g.text
    gid = g.json()["gate_id"]
    c = client.post("/api/cards", headers=admin, json={
        "emp_id": 2, "card_no": "GS-APIC", "expiry_date": str(date.today() + timedelta(days=30))})
    assert c.status_code == 201, c.text
    cid = c.json()["card_id"]
    try:
        r = client.put(f"/api/gates/{gid}", headers=admin, json={
            "gate_name": "Test Gate 2", "location": "Lab", "type": "EXIT", "status": "MAINTENANCE"})
        assert r.json()["status"] == "MAINTENANCE"
        r = client.put(f"/api/cards/{cid}", headers=admin, json={
            "emp_id": 2, "card_no": "GS-APIC", "expiry_date": str(date.today() + timedelta(days=60)),
            "status": "LOST"})
        assert r.json()["status"] == "LOST"
        dup = client.post("/api/cards", headers=admin, json={
            "emp_id": 2, "card_no": "GS-APIC", "expiry_date": str(date.today() + timedelta(days=30))})
        assert dup.status_code == 409
    finally:
        assert client.delete(f"/api/cards/{cid}", headers=admin).status_code == 200
        assert client.delete(f"/api/gates/{gid}", headers=admin).status_code == 200


def test_record_scan_and_trigger(client, guard, admin):
    r = client.post("/api/access-logs", headers=guard, json={"card_no": "GS-1011", "gate_id": 1})
    assert r.status_code == 201 and r.json()["access_result"] == "DENIED"   # LOST card
    scan = r.json()["scan_id"]
    assert client.delete(f"/api/access-logs/{scan}", headers=admin).status_code == 200


def test_access_log_filters(client, guard):
    rows = client.get("/api/access-logs", headers=guard, params={"result": "DENIED"}).json()
    assert rows and all(r["access_result"] == "DENIED" for r in rows)
    rows = client.get("/api/access-logs", headers=guard,
                      params={"gate_id": 3, "sort": "scan_time", "order": "asc"}).json()
    assert all(r["gate_name"] == "Server Room" for r in rows)
    assert rows == sorted(rows, key=lambda r: r["scan_time"])


def test_restrict_delete_message(client, admin):
    r = client.delete("/api/cards/1", headers=admin)
    assert r.status_code == 409 and "deactivate" in r.json()["detail"]


@pytest.mark.parametrize("key", list(SQL_QUERIES))
def test_every_report_query_runs(client, admin, key):
    r = client.get(f"/api/analytics/sql/{key}", headers=admin)
    assert r.status_code == 200, r.text
    assert "rows" in r.json()


def test_join_query_results(client, admin):
    d = client.get("/api/analytics/sql/join_incident_details", headers=admin).json()
    assert {"incident_id", "gate_name", "card_holder", "card_no"} <= set(d["columns"])
    assert len(d["rows"]) >= 9


def test_recursive_trend_has_14_days(client, admin):
    d = client.get("/api/analytics/sql/recursive_daily_trend", headers=admin).json()
    assert len(d["rows"]) == 14


def test_recursive_burst_chain(client, admin):
    d = client.get("/api/analytics/sql/recursive_burst_chains", headers=admin).json()
    assert any(r["scans_in_chain"] >= 2 for r in d["rows"])


def test_recursive_burst_chain_terminates_on_equal_timestamps(su):
    """Two scans at the same gate with the SAME scan_time used to make the recursion loop forever."""
    su.execute("SET LOCAL statement_timeout = '5s'")
    su.execute("INSERT INTO access_logs (card_id, gate_id, scan_time) VALUES "
               "(1, 4, TIMESTAMP '2026-01-01 09:00:00'), (2, 4, TIMESTAMP '2026-01-01 09:00:00'), "
               "(3, 4, TIMESTAMP '2026-01-01 09:00:00')")
    rows = su.execute(SQL_QUERIES["recursive_burst_chains"]["sql"]).fetchall()
    assert any(r[1] == 4 and r[2] == 3 for r in rows)          # one chain of 3 scans at gate 4


def test_dashboard(client, guard):
    d = client.get("/api/dashboard", headers=guard).json()
    for k in ("employees", "cards", "gates", "scans", "incidents", "pending_alerts"):
        assert k in d["counts"]
    assert len(d["trend"]) == 14
