from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from ..auth import CurrentUser, get_current_user, require_admin, require_staff
from ..db import pg_session, rows
from ..deps import not_found, order_by
from ..schemas import ScanIn

router = APIRouter(prefix="/api/access-logs", tags=["Access Logs"])

SORTS = {"scan_id": "a.scan_id", "scan_time": "a.scan_time", "employee": "e.name",
         "gate": "g.gate_name", "result": "a.access_result", "card_no": "c.card_no"}


@router.get("")
def list_logs(search: str | None = None, gate_id: int | None = None,
              result: str | None = None, date_from: date | None = None,
              date_to: date | None = None, sort: str | None = None, order: str | None = "desc",
              limit: int = 500, user: CurrentUser = Depends(get_current_user)):
    """4-table INNER JOIN + correlated subquery counting incidents per scan."""
    sql = f"""
        SELECT a.scan_id, a.scan_time, a.access_result,
               c.card_id, c.card_no, e.emp_id, e.name AS employee, e.department,
               g.gate_id, g.gate_name,
               (SELECT COUNT(*) FROM incidents i WHERE i.scan_id = a.scan_id) AS incident_count
        FROM access_logs a
        JOIN cards     c ON c.card_id = a.card_id
        JOIN employees e ON e.emp_id  = c.emp_id
        JOIN gates     g ON g.gate_id = a.gate_id
        WHERE (CAST(:search AS text) IS NULL OR e.name ILIKE '%' || :search || '%'
               OR c.card_no ILIKE '%' || :search || '%')
          AND (CAST(:gate AS int) IS NULL OR a.gate_id = :gate)
          AND (CAST(:result AS text) IS NULL OR a.access_result = :result)
          AND (CAST(:dfrom AS date) IS NULL OR a.scan_time >= :dfrom)
          AND (CAST(:dto AS date) IS NULL OR a.scan_time < CAST(:dto AS date) + 1)
        {order_by(sort, order, SORTS, "a.scan_time")}
        LIMIT :limit"""
    with pg_session(user.role) as conn:
        return rows(conn.execute(text(sql), {
            "search": search or None, "gate": gate_id, "result": result or None,
            "dfrom": date_from, "dto": date_to, "limit": min(max(limit, 1), 2000)}))


@router.post("", status_code=201)
def record_scan(body: ScanIn, user: CurrentUser = Depends(require_staff)):
    """Admin and security staff may record scans. trg_validate_access_log decides GRANTED/DENIED."""
    with pg_session(user.role) as conn:
        card = conn.execute(text("SELECT card_id FROM cards WHERE card_no = :n"),
                            {"n": body.card_no.strip().upper()}).scalar_one_or_none()
        if card is None:
            raise HTTPException(422, f"Card {body.card_no} is not registered")
        return rows(conn.execute(text("""
            INSERT INTO access_logs (card_id, gate_id, scan_time)
            VALUES (:c, :g, COALESCE(CAST(:t AS timestamp), LOCALTIMESTAMP))
            RETURNING *"""), {"c": card, "g": body.gate_id, "t": body.scan_time}))[0]


@router.get("/{scan_id}/authorized-count")
def authorized_count(scan_id: int, window: int = 10, user: CurrentUser = Depends(get_current_user)):
    with pg_session(user.role) as conn:
        exists = conn.execute(text("SELECT 1 FROM access_logs WHERE scan_id = :s"),
                              {"s": scan_id}).scalar_one_or_none()
        if not exists:
            raise not_found("Scan", scan_id)
        n = conn.execute(text("SELECT fn_authorized_count(:s, :w)"),
                         {"s": scan_id, "w": window}).scalar_one()
    return {"scan_id": scan_id, "window_seconds": window, "authorized_count": n}


@router.delete("/{scan_id}")
def delete_log(scan_id: int, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        n = conn.execute(text("DELETE FROM access_logs WHERE scan_id = :id"),
                         {"id": scan_id}).rowcount
    if not n:
        raise not_found("Scan", scan_id)
    return {"deleted": scan_id}
