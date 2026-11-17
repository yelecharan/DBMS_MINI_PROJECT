-- =====================================================================
-- GateSentry - 02_functions_triggers.sql
-- Stored functions, procedures and triggers (Advanced SQL)
-- =====================================================================

-- =====================================================================
-- TRIGGER 1: total participation  Employees ==has== Cards
-- Every employee must own at least one card. Checked at COMMIT time
-- (DEFERRABLE INITIALLY DEFERRED) so an employee and the first card can be
-- inserted inside the same transaction.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_check_employee_has_card()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_emp INT;
BEGIN
    IF TG_TABLE_NAME = 'employees' THEN
        v_emp := NEW.emp_id;
    ELSE
        v_emp := OLD.emp_id;           -- card deleted or moved to another employee
    END IF;

    -- employee deleted in the same transaction (cascade) -> nothing to check
    IF NOT EXISTS (SELECT 1 FROM employees WHERE emp_id = v_emp) THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM cards WHERE emp_id = v_emp) THEN
        RAISE EXCEPTION 'Employee % must own at least one access card (total participation)', v_emp
              USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_employee_requires_card
    AFTER INSERT ON employees
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_check_employee_has_card();

CREATE CONSTRAINT TRIGGER trg_card_removal_keeps_one
    AFTER DELETE OR UPDATE OF emp_id ON cards
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_check_employee_has_card();

-- =====================================================================
-- TRIGGER 2: cards past their expiry date are marked EXPIRED automatically
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_card_auto_expire()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.expiry_date < CURRENT_DATE AND NEW.status = 'ACTIVE' THEN
        NEW.status := 'EXPIRED';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_card_auto_expire
    BEFORE INSERT OR UPDATE ON cards
    FOR EACH ROW EXECUTE FUNCTION fn_card_auto_expire();

-- =====================================================================
-- TRIGGER 3: validate every card scan
-- A scan with an inactive/expired/lost card or at a gate that is not
-- ACTIVE is forced to 'DENIED', whatever the client sent.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_validate_access_log()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_card_status  VARCHAR;
    v_expiry       DATE;
    v_gate_status  VARCHAR;
BEGIN
    SELECT status, expiry_date INTO v_card_status, v_expiry FROM cards WHERE card_id = NEW.card_id;
    SELECT status INTO v_gate_status FROM gates WHERE gate_id = NEW.gate_id;

    IF v_card_status IS DISTINCT FROM 'ACTIVE'
       OR v_expiry < NEW.scan_time::date
       OR v_gate_status IS DISTINCT FROM 'ACTIVE' THEN
        NEW.access_result := 'DENIED';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_access_log
    BEFORE INSERT ON access_logs
    FOR EACH ROW EXECUTE FUNCTION fn_validate_access_log();

-- =====================================================================
-- TRIGGER 4: an incident cannot be detected before the scan it refers to
-- (a cross-table rule that a CHECK constraint cannot express)
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_validate_incident_time()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_scan_time TIMESTAMP;
BEGIN
    SELECT scan_time INTO v_scan_time FROM access_logs WHERE scan_id = NEW.scan_id;
    IF NEW.detected_time < v_scan_time THEN
        RAISE EXCEPTION 'detected_time (%) cannot be earlier than scan_time (%) of scan %',
              NEW.detected_time, v_scan_time, NEW.scan_id
              USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_incident_time
    BEFORE INSERT OR UPDATE OF detected_time, scan_id ON incidents
    FOR EACH ROW EXECUTE FUNCTION fn_validate_incident_time();

-- =====================================================================
-- FUNCTION: number of authorised (GRANTED) scans at the same gate within
-- +/- p_window seconds of a scan. This is the "authorized_count" that the
-- guard compares with the number of people observed walking through.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_authorized_count(p_scan_id INT, p_window INT DEFAULT 10)
RETURNS INT LANGUAGE sql STABLE AS $$
    SELECT COUNT(*)::INT
    FROM access_logs a
    JOIN access_logs s ON s.scan_id = p_scan_id
    WHERE a.gate_id = s.gate_id
      AND a.access_result = 'GRANTED'
      AND a.scan_time BETWEEN s.scan_time - make_interval(secs => p_window)
                          AND s.scan_time + make_interval(secs => p_window);
$$;

-- FUNCTION: severity from the number of extra (unauthorised) people
CREATE OR REPLACE FUNCTION fn_compute_severity(p_observed INT, p_authorized INT)
RETURNS VARCHAR LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_excess INT := p_observed - p_authorized;
BEGIN
    RETURN CASE
        WHEN v_excess <= 0 THEN NULL
        WHEN v_excess = 1  THEN 'LOW'
        WHEN v_excess = 2  THEN 'MEDIUM'
        WHEN v_excess <= 4 THEN 'HIGH'
        ELSE 'CRITICAL'
    END;
END;
$$;

-- =====================================================================
-- FUNCTION: report a suspected tailgating event.
-- Compares observed people with authorised scans and, if more people
-- entered, creates the incident and returns its id.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_report_tailgating(
    p_scan_id    INT,
    p_observed   INT,
    p_authorized INT DEFAULT NULL)
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_auth      INT;
    v_incident  INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM access_logs WHERE scan_id = p_scan_id) THEN
        RAISE EXCEPTION 'Scan % does not exist', p_scan_id USING ERRCODE = 'foreign_key_violation';
    END IF;

    v_auth := COALESCE(p_authorized, fn_authorized_count(p_scan_id));

    IF p_observed <= v_auth THEN
        RAISE EXCEPTION 'No tailgating: % people observed, % authorised scans', p_observed, v_auth
              USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO incidents(scan_id, detected_time, severity, status)
    VALUES (p_scan_id,
            GREATEST(CURRENT_TIMESTAMP::timestamp, (SELECT scan_time FROM access_logs WHERE scan_id = p_scan_id)),
            fn_compute_severity(p_observed, v_auth),
            'OPEN')
    RETURNING incident_id INTO v_incident;

    RETURN v_incident;
END;
$$;

-- =====================================================================
-- PROCEDURE: add an employee together with the first access card
-- (needed because of total participation Employees ==has== Cards)
-- =====================================================================
CREATE OR REPLACE PROCEDURE sp_add_employee_with_card(
    p_name       VARCHAR,
    p_department VARCHAR,
    p_phone      VARCHAR,
    p_card_no    VARCHAR,
    p_expiry     DATE,
    INOUT p_emp_id INT DEFAULT NULL)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO employees(name, department, phone)
    VALUES (p_name, p_department, p_phone)
    RETURNING emp_id INTO p_emp_id;

    INSERT INTO cards(emp_id, card_no, issue_date, expiry_date, status)
    VALUES (p_emp_id, p_card_no, CURRENT_DATE, p_expiry, 'ACTIVE');
END;
$$;

-- PROCEDURE: block all cards of an employee (e.g. employee left / card stolen)
CREATE OR REPLACE PROCEDURE sp_deactivate_employee_cards(p_emp_id INT, INOUT p_count INT DEFAULT 0)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE cards SET status = 'INACTIVE'
    WHERE emp_id = p_emp_id AND status = 'ACTIVE';
    GET DIAGNOSTICS p_count = ROW_COUNT;
END;
$$;

-- =====================================================================
-- FUNCTION (uses CTEs): per-gate risk summary used by the dashboard
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_gate_risk_summary()
RETURNS TABLE (gate_id INT, gate_name VARCHAR, total_scans BIGINT,
               denied_scans BIGINT, incidents BIGINT, risk_score NUMERIC)
LANGUAGE sql STABLE AS $$
    WITH scan_stats AS (
        SELECT gate_id,
               COUNT(*)                                          AS total_scans,
               COUNT(*) FILTER (WHERE access_result = 'DENIED')  AS denied_scans
        FROM access_logs
        GROUP BY gate_id
    ),
    incident_stats AS (
        SELECT a.gate_id, COUNT(i.incident_id) AS incidents
        FROM incidents i
        JOIN access_logs a ON a.scan_id = i.scan_id
        GROUP BY a.gate_id
    )
    SELECT g.gate_id,
           g.gate_name,
           COALESCE(s.total_scans, 0),
           COALESCE(s.denied_scans, 0),
           COALESCE(n.incidents, 0),
           ROUND(100.0 * COALESCE(n.incidents, 0) / NULLIF(s.total_scans, 0), 2)
    FROM gates g
    LEFT JOIN scan_stats     s ON s.gate_id = g.gate_id
    LEFT JOIN incident_stats n ON n.gate_id = g.gate_id
    ORDER BY 6 DESC NULLS LAST, g.gate_id;
$$;
