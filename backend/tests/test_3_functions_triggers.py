"""Stored functions, procedures and triggers (all rolled back)."""
import pytest
from psycopg import errors


def one(su, sql, params=None):
    return su.execute(sql, params).fetchone()[0]


def test_trigger_card_auto_expire(su):
    status = one(su, "INSERT INTO cards(emp_id, card_no, issue_date, expiry_date) "
                     "VALUES (2, 'GS-T10', CURRENT_DATE - 100, CURRENT_DATE - 1) RETURNING status")
    assert status == "EXPIRED"


def test_trigger_denies_inactive_card(su):
    # GS-1008 is INACTIVE in the seed data
    res = one(su, "INSERT INTO access_logs(card_id, gate_id, access_result) "
                  "VALUES ((SELECT card_id FROM cards WHERE card_no='GS-1008'), 1, 'GRANTED') "
                  "RETURNING access_result")
    assert res == "DENIED"


def test_trigger_denies_gate_in_maintenance(su):
    res = one(su, "INSERT INTO access_logs(card_id, gate_id) VALUES (1, "
                  "(SELECT gate_id FROM gates WHERE status='MAINTENANCE' LIMIT 1)) RETURNING access_result")
    assert res == "DENIED"


def test_trigger_grants_valid_scan(su):
    assert one(su, "INSERT INTO access_logs(card_id, gate_id) VALUES (1, 1) RETURNING access_result") == "GRANTED"


def test_trigger_incident_before_scan_rejected(su):
    with pytest.raises(errors.CheckViolation):
        su.execute("INSERT INTO incidents(scan_id, detected_time) "
                   "VALUES (1, (SELECT scan_time - INTERVAL '1 hour' FROM access_logs WHERE scan_id = 1))")


@pytest.mark.parametrize("obs,auth,expected", [(2, 1, "LOW"), (3, 1, "MEDIUM"), (5, 1, "HIGH"),
                                               (9, 1, "CRITICAL"), (1, 1, None)])
def test_fn_compute_severity_values(su, obs, auth, expected):
    assert one(su, "SELECT fn_compute_severity(%s, %s)", (obs, auth)) == expected


def test_fn_authorized_count_burst(su):
    # seed scans 1 and 2 are 5 s apart at the Main Lobby Gate
    assert one(su, "SELECT fn_authorized_count(1)") == 2
    assert one(su, "SELECT fn_authorized_count(4)") == 1


def test_fn_report_tailgating_creates_incident(su):
    inc = one(su, "SELECT fn_report_tailgating(30, 4)")
    row = su.execute("SELECT scan_id, severity, status FROM incidents WHERE incident_id=%s", (inc,)).fetchone()
    assert row == (30, "HIGH", "OPEN")


def test_fn_report_tailgating_rejects_no_excess(su):
    with pytest.raises(errors.CheckViolation):
        su.execute("SELECT fn_report_tailgating(1, 2)")


def test_procedure_add_employee_with_card(su):
    emp = one(su, "CALL sp_add_employee_with_card('Proc Test','Finance','9000033333','GS-T11', CURRENT_DATE+90, NULL)")
    assert one(su, "SELECT COUNT(*) FROM cards WHERE emp_id=%s AND status='ACTIVE'", (emp,)) == 1
    su.execute("SET CONSTRAINTS ALL IMMEDIATE")      # participation satisfied


def test_procedure_deactivate_cards(su):
    assert one(su, "CALL sp_deactivate_employee_cards(3, NULL)") == 1
    assert one(su, "SELECT status FROM cards WHERE emp_id = 3") == "INACTIVE"


def test_fn_gate_risk_summary(su):
    rows = su.execute("SELECT gate_name, incidents FROM fn_gate_risk_summary()").fetchall()
    assert len(rows) >= 5
    assert rows[0][0] == "Server Room"
