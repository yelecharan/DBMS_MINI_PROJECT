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


def mongo_counts_by_incident(collection: str, ids: list[int]) -> dict[int, int]:
    pipeline = [{"$match": {"incident_id": {"$in": ids}}},
                {"$group": {"_id": "$incident_id", "n": {"$sum": 1}}}]
    return {d["_id"]: d["n"] for d in mongo_db[collection].aggregate(pipeline)}
