from fastapi import HTTPException

from .db import mongo_db, pg_session, rows
from sqlalchemy import text


def order_by(sort: str | None, order: str | None, allowed: dict[str, str], default: str) -> str:
    """Build a safe ORDER BY from a whitelist (user input never reaches SQL text)."""
    column = allowed.get(sort or "", default)
    direction = "DESC" if (order or "").lower() == "desc" else "ASC"
    return f"ORDER BY {column} {direction} NULLS LAST"


def not_found(what: str, key) -> HTTPException:
    return HTTPException(404, f"{what} {key} not found")


def ensure_incident_exists(role: str, incident_id: int) -> dict:
    """Application-level referential integrity: MongoDB docs must point to a real SQL incident."""
    with pg_session(role) as conn:
        found = rows(conn.execute(text("""
            SELECT i.incident_id, i.severity, i.status, a.scan_id, a.gate_id, g.gate_name
            FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id
            JOIN gates g ON g.gate_id = a.gate_id
            WHERE i.incident_id = :id"""), {"id": incident_id}))
    if not found:
        raise HTTPException(422, f"incident_id {incident_id} does not exist in PostgreSQL")
    return found[0]


INCIDENTS_UNDER = {
    # which incidents disappear (ON DELETE CASCADE) when a row of this kind is deleted
    "employee": "SELECT i.incident_id FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id "
                "JOIN cards c ON c.card_id = a.card_id WHERE c.emp_id = :id",
    "card": "SELECT i.incident_id FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id "
            "WHERE a.card_id = :id",
    "gate": "SELECT i.incident_id FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id "
            "WHERE a.gate_id = :id",
    "scan": "SELECT incident_id FROM incidents WHERE scan_id = :id",
}


def cascading_delete(conn, kind: str, delete_sql: str, key: int) -> dict:
    """Delete a SQL row and everything under it.

    PostgreSQL cascades through cards -> access_logs -> incidents by itself (ON DELETE CASCADE).
    MongoDB cannot see those foreign keys, so the incident ids are collected first and their
    Observations / Report / Alerts documents are deleted inside the same SQL transaction
    (if MongoDB fails, the SQL delete is rolled back too).
    """
    from .mongo_setup import ALERTS, OBSERVATIONS, REPORT
    ids = [r[0] for r in conn.execute(text(INCIDENTS_UNDER[kind]), {"id": key})]
    deleted = conn.execute(text(delete_sql), {"id": key}).rowcount
    if not deleted:
        return {"deleted": 0}
    # run the deferred participation trigger NOW (not at COMMIT), so a refused delete
    # fails before any MongoDB document is touched
    conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    removed = {c: (mongo_db[c].delete_many({"incident_id": {"$in": ids}}).deleted_count if ids else 0)
               for c in (OBSERVATIONS, REPORT, ALERTS)}
    return {"deleted": key, "incidents_removed": len(ids), "mongo_documents_removed": removed}


def mongo_counts_by_incident(collection: str, ids: list[int]) -> dict[int, int]:
    pipeline = [{"$match": {"incident_id": {"$in": ids}}},
                {"$group": {"_id": "$incident_id", "n": {"$sum": 1}}}]
    return {d["_id"]: d["n"] for d in mongo_db[collection].aggregate(pipeline)}
