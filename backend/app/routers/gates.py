from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import pg_session, rows
from ..deps import cascading_delete, not_found, order_by
from ..schemas import GateIn

router = APIRouter(prefix="/api/gates", tags=["Gates"])

SORTS = {"gate_id": "g.gate_id", "gate_name": "g.gate_name", "location": "g.location",
         "type": "g.type", "status": "g.status", "scans": "scan_count",
         "incidents": "incident_count"}


@router.get("")
def list_gates(search: str | None = None, status: str | None = None,
               sort: str | None = None, order: str | None = None,
               user: CurrentUser = Depends(get_current_user)):
    sql = f"""
        SELECT g.gate_id, g.gate_name, g.location, g.type, g.status,
               COUNT(DISTINCT a.scan_id)     AS scan_count,
               COUNT(DISTINCT i.incident_id) AS incident_count
        FROM gates g
        LEFT JOIN access_logs a ON a.gate_id = g.gate_id
        LEFT JOIN incidents   i ON i.scan_id = a.scan_id
        WHERE (CAST(:search AS text) IS NULL OR g.gate_name ILIKE '%' || :search || '%'
               OR g.location ILIKE '%' || :search || '%')
          AND (CAST(:status AS text) IS NULL OR g.status = :status)
        GROUP BY g.gate_id
        {order_by(sort, order, SORTS, "g.gate_id")}"""
    with pg_session(user.role) as conn:
        return rows(conn.execute(text(sql), {"search": search or None, "status": status or None}))


@router.post("", status_code=201)
def create_gate(body: GateIn, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        return rows(conn.execute(text("""
            INSERT INTO gates (gate_name, location, type, status)
            VALUES (:n, :l, :t, :s) RETURNING *"""),
            {"n": body.gate_name.strip(), "l": body.location.strip(), "t": body.type,
             "s": body.status}))[0]


@router.put("/{gate_id}")
def update_gate(gate_id: int, body: GateIn, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        res = rows(conn.execute(text("""
            UPDATE gates SET gate_name = :n, location = :l, type = :t, status = :s
            WHERE gate_id = :id RETURNING *"""),
            {"n": body.gate_name.strip(), "l": body.location.strip(), "t": body.type,
             "s": body.status, "id": gate_id}))
    if not res:
        raise not_found("Gate", gate_id)
    return res[0]


@router.delete("/{gate_id}")
def delete_gate(gate_id: int, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        result = cascading_delete(conn, "gate", "DELETE FROM gates WHERE gate_id = :id", gate_id)
    if not result["deleted"]:
        raise not_found("Gate", gate_id)
    return result
