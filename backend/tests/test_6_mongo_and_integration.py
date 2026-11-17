"""MongoDB CRUD + aggregation, and SQL <-> MongoDB integration through incident_id."""
from datetime import datetime, timezone

import pytest
from pymongo.errors import WriteError


def test_validator_rejects_bad_document(mdb):
    with pytest.raises(WriteError):
        mdb.Observations.insert_one({"obs_id": "BAD", "incident_id": 1, "method": "CCTV",
                                     "observed_count": -1, "authorized_count": 1,
                                     "timestamp": datetime.now(timezone.utc)})


def test_observation_crud(client, guard, admin):
    r = client.post("/api/observations", headers=guard, json={
        "incident_id": 1, "method": "GUARD_PATROL", "observed_count": 5,
        "authorized_count": 2, "notes": "pytest", "tags": ["Test", " "]})
    assert r.status_code == 201, r.text
    obs = r.json()
    assert obs["location"]["gate_name"] == "Main Lobby Gate" and obs["tags"] == ["test"]
    oid = obs["obs_id"]
    found = client.get("/api/observations", headers=guard,
                       params={"incident_id": 1, "min_excess": 3}).json()
    assert any(o["obs_id"] == oid for o in found)
    r = client.put(f"/api/observations/{oid}", headers=guard, json={
        "method": "SIMULATED", "observed_count": 6, "authorized_count": 2, "notes": "edited", "tags": []})
    assert r.json()["observed_count"] == 6 and r.json()["updated_by"] == "guard"
    assert client.delete(f"/api/observations/{oid}", headers=guard).status_code == 403
    assert client.delete(f"/api/observations/{oid}", headers=admin).status_code == 200
    assert client.delete(f"/api/observations/{oid}", headers=admin).status_code == 404


def test_report_crud_with_arrays_and_text_search(client, guard, admin):
    r = client.post("/api/reports", headers=guard, json={
        "incident_id": 2, "description": "Pytest zebra report about the server room door.",
        "attachments": [{"file_name": "a.pdf", "file_type": "application/pdf"}]})
    assert r.status_code == 201, r.text
    rid = r.json()["report_id"]
    try:
        assert client.get("/api/reports", headers=guard, params={"search": "zebra"}).json()[0]["report_id"] == rid
        r = client.post(f"/api/reports/{rid}/attachments", headers=guard,
                        json={"file_name": "b.jpg", "file_type": "image/jpeg"})
        assert len(r.json()["attachments"]) == 2                       # $push
        r = client.delete(f"/api/reports/{rid}/attachments/a.pdf", headers=guard)
        assert [a["file_name"] for a in r.json()["attachments"]] == ["b.jpg"]   # $pull
        r = client.put(f"/api/reports/{rid}", headers=guard,
                       json={"description": "Updated description for pytest."})
        assert r.json()["description"].startswith("Updated")
        stats = client.get("/api/reports/stats", headers=guard).json()
        assert stats["by_reporter"]
    finally:
        assert client.delete(f"/api/reports/{rid}", headers=admin).status_code == 200


def test_alert_create_ack_delete(client, guard, admin):
    r = client.post("/api/alerts", headers=admin, json={
        "incident_id": 3, "alert_type": "SYSTEM", "message": "pytest alert"})
    assert r.status_code == 201
    aid = r.json()["alert_id"]
    try:
        r = client.patch(f"/api/alerts/{aid}/ack", headers=guard, json={"comment": "seen"})
        assert r.json()["ack_status"] == "ACKNOWLEDGED" and r.json()["acknowledged"]["by"] == "guard"
        assert client.patch(f"/api/alerts/{aid}/ack", headers=guard, json={}).status_code == 409
        assert client.post(f"/api/alerts/{aid}/reopen", headers=admin).json()["ack_status"] == "PENDING"
        assert client.get("/api/alerts", headers=guard, params={"ack_status": "PENDING"}).json()
    finally:
        assert client.delete(f"/api/alerts/{aid}", headers=admin).status_code == 200


def test_aggregations(client, admin):
    s = client.get("/api/observations/stats", headers=admin).json()
    assert s["per_gate"][0]["gate"] == "Server Room"
    a = client.get("/api/alerts/summary", headers=admin).json()
    assert a["by_status"] and "pending_with_observations" in a
    for key in client.get("/api/analytics/mongo", headers=admin).json():
        r = client.get(f"/api/analytics/mongo/{key['key']}", headers=admin)
        assert r.status_code == 200, r.text


def test_reference_to_missing_incident_rejected(client, guard):
    r = client.post("/api/observations", headers=guard, json={
        "incident_id": 999999, "observed_count": 3, "authorized_count": 1})
    assert r.status_code == 422 and "does not exist" in r.json()["detail"]


def test_report_tailgating_end_to_end(client, guard, admin, su, mdb):
    """SQL function creates the incident; Mongo gets Observation + Alert; delete cascades."""
    r = client.post("/api/incidents/report-tailgating", headers=guard, json={
        "scan_id": 30, "observed_count": 4, "method": "MANUAL_HEADCOUNT", "notes": "pytest"})
    assert r.status_code == 201, r.text
    body = r.json()
    inc = body["incident"]["incident_id"]
    assert body["incident"]["severity"] == "HIGH" and body["authorized_count"] == 1
    assert su.execute("SELECT status FROM incidents WHERE incident_id=%s", (inc,)).fetchone()[0] == "OPEN"
    assert mdb.Observations.count_documents({"incident_id": inc}) == 1
    assert mdb.Alerts.count_documents({"incident_id": inc, "ack_status": "PENDING"}) == 1
    detail = client.get(f"/api/incidents/{inc}", headers=guard).json()
    assert len(detail["observations"]) == 1 and len(detail["alerts"]) == 1
    listed = [i for i in client.get("/api/incidents", headers=guard).json() if i["incident_id"] == inc]
    assert listed[0]["pending_alerts"] == 1

    r = client.delete(f"/api/incidents/{inc}", headers=admin)
    assert r.status_code == 200
    assert r.json()["mongo_documents_removed"] == {"Observations": 1, "Report": 0, "Alerts": 1}
    assert mdb.Observations.count_documents({"incident_id": inc}) == 0


def test_no_tailgating_creates_nothing(client, guard, mdb):
    before = mdb.Alerts.count_documents({})
    r = client.post("/api/incidents/report-tailgating", headers=guard,
                    json={"scan_id": 1, "observed_count": 2})
    assert r.status_code == 400 and "No tailgating" in r.json()["detail"]
    assert mdb.Alerts.count_documents({}) == before


def test_every_mongo_doc_references_existing_incident(su, mdb):
    sql_ids = {r[0] for r in su.execute("SELECT incident_id FROM incidents")}
    for coll in ("Observations", "Report", "Alerts"):
        assert set(mdb[coll].distinct("incident_id")) <= sql_ids
