"""PK / FK / UNIQUE / CHECK / NOT NULL / participation constraints (all rolled back)."""
import psycopg
import pytest
from psycopg import errors


def test_unique_phone(su):
    with pytest.raises(errors.UniqueViolation):
        su.execute("CALL sp_add_employee_with_card('Dup Phone','HR','9876543210','GS-T1', CURRENT_DATE+30, NULL)")


def test_check_phone_format(su):
    with pytest.raises(errors.CheckViolation):
        su.execute("CALL sp_add_employee_with_card('Bad Phone','HR','12ab','GS-T2', CURRENT_DATE+30, NULL)")


def test_check_card_dates(su):
    with pytest.raises(errors.CheckViolation):
        su.execute("INSERT INTO cards(emp_id, card_no, issue_date, expiry_date) "
                   "VALUES (1, 'GS-T3', CURRENT_DATE, CURRENT_DATE - 1)")


def test_check_card_status(su):
    with pytest.raises(errors.CheckViolation):
        su.execute("INSERT INTO cards(emp_id, card_no, expiry_date, status) "
                   "VALUES (1, 'GS-T4', CURRENT_DATE + 10, 'STOLEN')")


def test_foreign_key_card_employee(su):
    with pytest.raises(errors.ForeignKeyViolation):
        su.execute("INSERT INTO cards(emp_id, card_no, expiry_date) VALUES (99999, 'GS-T5', CURRENT_DATE+10)")


def test_not_null_scan_gate(su):
    with pytest.raises(errors.NotNullViolation):
        su.execute("INSERT INTO access_logs(card_id, gate_id) VALUES (1, NULL)")


def test_restrict_delete_card_with_scans(su):
    with pytest.raises(errors.RestrictViolation):
        su.execute("DELETE FROM cards WHERE card_id = 1")


def test_incident_severity_check(su):
    with pytest.raises(errors.CheckViolation):
        su.execute("INSERT INTO incidents(scan_id, severity) VALUES (1, 'EXTREME')")


def test_total_participation_employee_needs_card(su):
    """Deferred constraint trigger fires at COMMIT when an employee has no card."""
    su.execute("INSERT INTO employees(name, department, phone) VALUES ('No Card', 'HR', '9000011111')")
    with pytest.raises(psycopg.errors.CheckViolation):
        su.commit()


def test_total_participation_cannot_remove_last_card(su):
    # employee 2 has exactly one card (GS-1002) which has scans -> use a fresh employee
    su.execute("CALL sp_add_employee_with_card('Temp Emp','HR','9000022222','GS-T6', CURRENT_DATE+30, NULL)")
    su.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(psycopg.errors.CheckViolation):
        su.execute("DELETE FROM cards WHERE card_no = 'GS-T6'")
