from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import pg_session, rows
from ..deps import cascading_delete, not_found, order_by
from ..schemas import EmployeeCreate, EmployeeUpdate

router = APIRouter(prefix="/api/employees", tags=["Employees"])

SORTS = {"emp_id": "e.emp_id", "name": "e.name", "department": "e.department",
         "cards": "card_count", "scans": "scan_count"}


@router.get("")
def list_employees(search: str | None = None, department: str | None = None,
                   sort: str | None = None, order: str | None = None,
                   user: CurrentUser = Depends(get_current_user)):
    # viewers have no SELECT privilege on employees.phone (column-level GRANT)
    can_see_phone = user.role != "viewer"
    phone_col = "e.phone" if can_see_phone else "NULL::varchar AS phone"
    phone_search = "OR e.phone LIKE '%' || :search || '%'" if can_see_phone else ""
    sql = f"""
        SELECT e.emp_id, e.name, e.department, {phone_col},
               COUNT(DISTINCT c.card_id)                                   AS card_count,
               COUNT(DISTINCT c.card_id) FILTER (WHERE c.status = 'ACTIVE') AS active_cards,
               COUNT(a.scan_id)                                            AS scan_count,
               STRING_AGG(DISTINCT c.card_no, ', ')                        AS card_numbers
        FROM employees e
        LEFT JOIN cards c       ON c.emp_id  = e.emp_id
        LEFT JOIN access_logs a ON a.card_id = c.card_id
        WHERE (CAST(:search AS text) IS NULL OR e.name ILIKE '%' || :search || '%'
               {phone_search})
          AND (CAST(:dept AS text) IS NULL OR e.department = :dept)
        GROUP BY e.emp_id, e.name, e.department
        {order_by(sort, order, SORTS, "e.emp_id")}"""
    with pg_session(user.role) as conn:
        return rows(conn.execute(text(sql), {"search": search or None, "dept": department or None}))


@router.get("/departments")
def departments(user: CurrentUser = Depends(get_current_user)):
    with pg_session(user.role) as conn:
        return [r[0] for r in conn.execute(text(
            "SELECT DISTINCT department FROM employees ORDER BY 1"))]


@router.post("", status_code=201)
def create_employee(body: EmployeeCreate, user: CurrentUser = Depends(require_admin)):
    """Uses stored procedure sp_add_employee_with_card (employee + first card, one transaction)."""
    with pg_session(user.role) as conn:
        emp_id = conn.execute(text(
            "CALL sp_add_employee_with_card(:n, :d, :p, :c, :x, NULL)"),
            {"n": body.name.strip(), "d": body.department.strip(), "p": body.phone,
             "c": body.card_no.strip().upper(), "x": body.expiry_date}).scalar_one()
    return {"emp_id": emp_id}


@router.put("/{emp_id}")
def update_employee(emp_id: int, body: EmployeeUpdate, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        res = rows(conn.execute(text("""
            UPDATE employees SET name = :n, department = :d, phone = :p
            WHERE emp_id = :id RETURNING *"""),
            {"n": body.name.strip(), "d": body.department.strip(), "p": body.phone, "id": emp_id}))
    if not res:
        raise not_found("Employee", emp_id)
    return res[0]


@router.post("/{emp_id}/deactivate-cards")
def deactivate_cards(emp_id: int, user: CurrentUser = Depends(require_admin)):
    """Calls stored procedure sp_deactivate_employee_cards."""
    with pg_session(user.role) as conn:
        n = conn.execute(text("CALL sp_deactivate_employee_cards(:id, NULL)"),
                         {"id": emp_id}).scalar_one()
    return {"deactivated": n}


@router.delete("/{emp_id}")
def delete_employee(emp_id: int, user: CurrentUser = Depends(require_admin)):
    with pg_session(user.role) as conn:
        result = cascading_delete(conn, "employee", "DELETE FROM employees WHERE emp_id = :id", emp_id)
    if not result["deleted"]:
        raise not_found("Employee", emp_id)
    return result
