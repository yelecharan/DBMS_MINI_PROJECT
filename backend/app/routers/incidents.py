"""Incidents live in PostgreSQL; their Observations / Report / Alerts live in MongoDB.
This router is where the two databases are tied together through incident_id."""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth import CurrentUser, get_current_user, require_admin, require_staff
from ..db import mongo_db, pg_session, rows
from ..deps import mongo_counts_by_incident, not_found, order_by
from ..mongo_setup import ALERTS, OBSERVATIONS, REPORT
from ..schemas import IncidentStatusIn, IncidentUpdate, TailgatingIn
from ..utils import new_id, utcnow

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

SORTS = {"incident_id": "i.incident_id", "detected_time": "i.detected_time",
         "severity": "array_position(ARRAY['LOW','MEDIUM','HIGH','CRITICAL'], i.severity::text)",
         "status": "i.status", "gate": "g.gate_name", "employee": "e.name"}

DETAIL_SQL = """
    SELECT i.incident_id, i.scan_id, i.detected_time, i.severity, i.status,
           a.scan_time, a.access_result, g.gate_id, g.gate_name, g.location,
           c.card_no, e.emp_id, e.name AS employee, e.department
    FROM incidents i
    JOIN access_logs a ON a.scan_id = i.scan_id
    JOIN gates       g ON g.gate_id = a.gate_id
    JOIN cards       c ON c.card_id = a.card_id
    JOIN employees   e ON e.emp_id  = c.emp_id
"""


@router.get("")
def list_incidents(search: str | None = None, severity: str | None = None,
                   status: str | None = None, sort: str | None = None,
                   order: str | None = "desc", user: CurrentUser = Depends(get_current_user)):
    sql = DETAIL_SQL + f"""
        WHERE (CAST(:search AS text) IS NULL OR e.name ILIKE '%' || :search || '%'
               OR g.gate_name ILIKE '%' || :search || '%' OR c.card_no ILIKE '%' || :search || '%')
          AND (CAST(:sev AS text) IS NULL OR i.severity = :sev)
          AND (CAST(:st AS text) IS NULL OR i.status = :st)
        {order_by(sort, order, SORTS, "i.detected_time")}"""
    with pg_session(user.role) as conn:
        data = rows(conn.execute(text(sql), {"search": search or None, "sev": severity or None,
                                             "st": status or None}))
    ids = [d["incident_id"] for d in data]
    obs, rep = mongo_counts_by_incident(OBSERVATIONS, ids), mongo_counts_by_incident(REPORT, ids)
    pend = {d["_id"]: d["n"] for d in mongo_db[ALERTS].aggregate([
        {"$match": {"incident_id": {"$in": ids}, "ack_status": "PENDING"}},
        {"$group": {"_id": "$incident_id", "n": {"$sum": 1}}}])}
    for d in data:
        d["observations"] = obs.get(d["incident_id"], 0)
        d["reports"] = rep.get(d["incident_id"], 0)
        d["pending_alerts"] = pend.get(d["incident_id"], 0)
    return data


@router.get("/{incident_id}")
def incident_detail(incident_id: int, user: CurrentUser = Depends(get_current_user)):
    """One incident from PostgreSQL + every MongoDB document that references it."""
    with pg_session(user.role) as conn:
        res = rows(conn.execute(text(DETAIL_SQL + " WHERE i.incident_id = :id"),
                                {"id": incident_id}))
    if not res:
        raise not_found("Incident", incident_id)
    q, proj = {"incident_id": incident_id}, {"_id": 0}
    return {
        "incident": res[0],
        "observations": list(mongo_db[OBSERVATIONS].find(q, proj).sort("timestamp", -1)),
        "reports": list(mongo_db[REPORT].find(q, proj).sort("timestamp", -1)),
        "alerts": list(mongo_db[ALERTS].find(q, proj).sort("alert_time", -1)),
    }


@router.post("/report-tailgating", status_code=201)
def report_tailgating(body: TailgatingIn, user: CurrentUser = Depends(require_staff)):
    """Security staff / admin: observed people > authorised scans.

    1. PostgreSQL : fn_report_tailgating() validates and inserts the incident
    2. MongoDB    : an Observation and an Alert document referencing incident_id
    The Mongo writes happen inside the open SQL transaction, so if MongoDB fails
    the SQL incident is rolled back as well (no orphan rows)."""
    with pg_session(user.role) as conn:
        auth = body.authorized_count
        if auth is None:
            auth = conn.execute(text("SELECT fn_authorized_count(:s)"),
                                {"s": body.scan_id}).scalar_one()
        incident_id = conn.execute(text("SELECT fn_report_tailgating(:s, :o, :a)"),
                                   {"s": body.scan_id, "o": body.observed_count,
                                    "a": auth}).scalar_one()
        inc = rows(conn.execute(text(DETAIL_SQL + " WHERE i.incident_id = :id"),
                                {"id": incident_id}))[0]
        now = utcnow()
        obs = {
            "obs_id": new_id("OBS"), "incident_id": incident_id, "method": body.method,
            "observed_count": body.observed_count, "authorized_count": auth, "timestamp": now,
            "location": {"gate_id": inc["gate_id"], "gate_name": inc["gate_name"],
                         "scan_id": body.scan_id},
            "observed_by": user.username, "notes": body.notes,
            "tags": ["tailgating", inc["severity"].lower()],
        }
        alert = {
            "alert_id": new_id("ALT"), "incident_id": incident_id, "alert_time": now,
            "alert_type": "ESCALATION" if inc["severity"] == "CRITICAL" else "TAILGATING",
            "severity": inc["severity"],
            "message": (f"{inc['severity']} tailgating suspected at {inc['gate_name']}: "
                        f"{body.observed_count} people on {auth} authorised scan(s)."),
            "ack_status": "PENDING", "acknowledged": None,
            "recipients": ["security-desk", "facility-admin"],
        }
        mongo_db[OBSERVATIONS].insert_one(obs)
        mongo_db[ALERTS].insert_one(alert)
    return {"incident": inc, "authorized_count": auth, "obs_id": obs["obs_id"],
            "alert_id": alert["alert_id"]}


@router.put("/{incident_id}")
def update_incident(incident_id: int, body: IncidentUpdate, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        res = rows(conn.execute(text("""
            UPDATE incidents SET severity = :sev, status = :st
            WHERE incident_id = :id RETURNING *"""),
            {"sev": body.severity, "st": body.status, "id": incident_id}))
    if not res:
        raise not_found("Incident", incident_id)
    return res[0]


@router.patch("/{incident_id}/status")
def update_status(incident_id: int, body: IncidentStatusIn,
                  user: CurrentUser = Depends(require_staff)):
    """Security staff hold a column-level UPDATE(status) privilege only."""
    with pg_session(user.role) as conn:
        res = rows(conn.execute(text("""
            UPDATE incidents SET status = :st WHERE incident_id = :id
            RETURNING incident_id, status"""), {"st": body.status, "id": incident_id}))
    if not res:
        raise not_found("Incident", incident_id)
    return res[0]


@router.delete("/{incident_id}")
def delete_incident(incident_id: int, user: CurrentUser = Depends(require_admin)):
    """Deletes the SQL row and cascades (application-level) to the MongoDB documents."""
    with pg_session(user.role) as conn:
        n = conn.execute(text("DELETE FROM incidents WHERE incident_id = :id"),
                         {"id": incident_id}).rowcount
        if not n:
            raise not_found("Incident", incident_id)
        removed = {c: mongo_db[c].delete_many({"incident_id": incident_id}).deleted_count
                   for c in (OBSERVATIONS, REPORT, ALERTS)}
    return {"deleted": incident_id, "mongo_documents_removed": removed}
