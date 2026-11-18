from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import pg_session, rows
from ..deps import cascading_delete, not_found, order_by
from ..schemas import CardIn

router = APIRouter(prefix="/api/cards", tags=["Cards"])

SORTS = {"card_id": "c.card_id", "card_no": "c.card_no", "employee": "e.name",
         "issue_date": "c.issue_date", "expiry_date": "c.expiry_date", "status": "c.status",
         "scans": "scan_count"}


@router.get("")
def list_cards(search: str | None = None, status: str | None = None,
               sort: str | None = None, order: str | None = None,
               user: CurrentUser = Depends(get_current_user)):
    sql = f"""
        SELECT c.card_id, c.card_no, c.emp_id, e.name AS employee, e.department,
               c.issue_date, c.expiry_date, c.status,
               (c.expiry_date - CURRENT_DATE) AS days_to_expiry,
               COUNT(a.scan_id) AS scan_count
        FROM cards c
        JOIN employees e        ON e.emp_id  = c.emp_id
        LEFT JOIN access_logs a ON a.card_id = c.card_id
        WHERE (CAST(:search AS text) IS NULL OR c.card_no ILIKE '%' || :search || '%'
               OR e.name ILIKE '%' || :search || '%')
          AND (CAST(:status AS text) IS NULL OR c.status = :status)
        GROUP BY c.card_id, e.name, e.department
        {order_by(sort, order, SORTS, "c.card_id")}"""
    with pg_session(user.role) as conn:
        return rows(conn.execute(text(sql), {"search": search or None, "status": status or None}))


@router.post("", status_code=201)
def create_card(body: CardIn, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        return rows(conn.execute(text("""
            INSERT INTO cards (emp_id, card_no, issue_date, expiry_date, status)
            VALUES (:e, :n, COALESCE(CAST(:i AS date), CURRENT_DATE), :x, :s)
            RETURNING *"""),
            {"e": body.emp_id, "n": body.card_no.strip().upper(), "i": body.issue_date,
             "x": body.expiry_date, "s": body.status}))[0]


@router.put("/{card_id}")
def update_card(card_id: int, body: CardIn, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        res = rows(conn.execute(text("""
            UPDATE cards SET emp_id = :e, card_no = :n,
                   issue_date = COALESCE(CAST(:i AS date), issue_date),
                   expiry_date = :x, status = :s
            WHERE card_id = :id RETURNING *"""),
            {"e": body.emp_id, "n": body.card_no.strip().upper(), "i": body.issue_date,
             "x": body.expiry_date, "s": body.status, "id": card_id}))
    if not res:
        raise not_found("Card", card_id)
    return res[0]


@router.delete("/{card_id}")
def delete_card(card_id: int, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        result = cascading_delete(conn, "card", "DELETE FROM cards WHERE card_id = :id", card_id)
    if not result["deleted"]:
        raise not_found("Card", card_id)
    return result
