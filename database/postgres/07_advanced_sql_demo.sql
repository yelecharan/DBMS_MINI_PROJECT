-- =====================================================================
-- GateSentry - 07_advanced_sql_demo.sql
-- Rubric item 8: "Advanced SQL concepts - Procedure/function, trigger, CTE"
-- Every stored function, procedure and trigger is CALLED here so you can
-- see it work, followed by CTEs and recursive CTEs.
--   A. list of all routines and triggers (catalog)
--   B. stored FUNCTIONS (4)            E. CTE and RECURSIVE CTE (3)
--   C. stored PROCEDURES (2)           F. bonus: VIEW, window functions, SAVEPOINT
--   D. TRIGGERS (5) - each one fired
-- The definitions are in 02_functions_triggers.sql.
--
-- HOW TO RUN (pgAdmin): right-click gatesentry -> Query Tool, open this file, press F5.
-- The whole file runs inside BEGIN ... ROLLBACK, so NOTHING is saved -
-- you can run it as many times as you like. Messages from RAISE NOTICE appear
-- in pgAdmin's "Messages" tab.
-- =====================================================================
BEGIN;


-- =====================================================================
-- A. WHAT ADVANCED OBJECTS EXIST?
-- =====================================================================
-- A.1 stored functions, trigger functions and procedures
SELECT CASE p.prokind WHEN 'p' THEN 'PROCEDURE'
                      ELSE CASE WHEN p.prorettype = 'trigger'::regtype THEN 'TRIGGER FUNCTION'
                                ELSE 'FUNCTION' END END     AS kind,
       p.proname                                            AS name,
       pg_get_function_arguments(p.oid)                     AS arguments,
       pg_get_function_result(p.oid)                        AS returns
FROM pg_proc p
WHERE p.pronamespace = 'public'::regnamespace
ORDER BY 1, 2;

-- A.2 triggers and the table/event they fire on
SELECT event_object_table AS table_name, trigger_name, action_timing AS timing,
       string_agg(event_manipulation, ' OR ') AS fires_on
FROM information_schema.triggers
WHERE trigger_schema = 'public'
GROUP BY event_object_table, trigger_name, action_timing
ORDER BY 1, 2;


-- =====================================================================
-- B. STORED FUNCTIONS
-- =====================================================================

-- ---------------------------------------------------------------------
-- B.1 fn_authorized_count(scan_id, window_seconds)
--     number of GRANTED scans at the same gate within +/- N seconds
-- ---------------------------------------------------------------------
SELECT a.scan_id, g.gate_name, a.scan_time,
       fn_authorized_count(a.scan_id)     AS authorised_within_10s,
       fn_authorized_count(a.scan_id, 60) AS authorised_within_60s
FROM access_logs a JOIN gates g ON g.gate_id = a.gate_id
WHERE a.scan_id IN (1, 2, 17, 18, 22)
ORDER BY a.scan_id;

-- ---------------------------------------------------------------------
-- B.2 fn_compute_severity(observed, authorised) -> LOW / MEDIUM / HIGH / CRITICAL
-- ---------------------------------------------------------------------
SELECT observed, authorised, observed - authorised AS extra_people,
       fn_compute_severity(observed, authorised) AS severity
FROM (VALUES (2, 1), (3, 1), (4, 1), (5, 1), (7, 1), (1, 1)) AS t(observed, authorised);

-- ---------------------------------------------------------------------
-- B.3 fn_report_tailgating(scan_id, observed, authorised)
--     validates the counts and INSERTS the incident, returns its id
-- ---------------------------------------------------------------------
SELECT fn_report_tailgating(30, 4) AS new_incident_id;          -- 4 people, 1 authorised -> HIGH
SELECT incident_id, scan_id, severity, status FROM incidents ORDER BY incident_id DESC LIMIT 1;

-- the function refuses when nobody extra walked in (error caught so the script continues)
DO $$
BEGIN
    PERFORM fn_report_tailgating(1, 2);                        -- 2 observed, 2 authorised
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'fn_report_tailgating rejected: %', SQLERRM;
END $$;

-- ---------------------------------------------------------------------
-- B.4 fn_gate_risk_summary()  - table-valued function built from 2 CTEs
-- ---------------------------------------------------------------------
SELECT * FROM fn_gate_risk_summary();


-- =====================================================================
-- C. STORED PROCEDURES
-- =====================================================================

-- ---------------------------------------------------------------------
-- C.1 sp_add_employee_with_card(name, dept, phone, card_no, expiry, OUT emp_id)
--     inserts the employee AND the first card in one transaction
-- ---------------------------------------------------------------------
CALL sp_add_employee_with_card('Demo Person', 'Engineering', '9000000001', 'GS-9001', CURRENT_DATE + 365, NULL);

SELECT e.emp_id, e.name, e.department, c.card_no, c.status
FROM employees e JOIN cards c ON c.emp_id = e.emp_id
WHERE e.phone = '9000000001';

-- ---------------------------------------------------------------------
-- C.2 sp_deactivate_employee_cards(emp_id, OUT count)
--     blocks every ACTIVE card of an employee
-- ---------------------------------------------------------------------
-- (CALL cannot take a sub-query as an argument, so the emp_id is looked up first)
DO $$
DECLARE
    v_emp   INT := (SELECT emp_id FROM employees WHERE phone = '9000000001');
    v_count INT;
BEGIN
    CALL sp_deactivate_employee_cards(v_emp, v_count);
    RAISE NOTICE 'sp_deactivate_employee_cards blocked % card(s) of employee %', v_count, v_emp;
END $$;

SELECT card_no, status FROM cards WHERE card_no = 'GS-9001';     -- now INACTIVE


-- =====================================================================
-- D. TRIGGERS - each one fired
-- =====================================================================

-- ---------------------------------------------------------------------
-- D.1 trg_card_auto_expire  (BEFORE INSERT/UPDATE ON cards)
--     we insert an ACTIVE card whose expiry date is in the past ...
-- ---------------------------------------------------------------------
INSERT INTO cards (emp_id, card_no, issue_date, expiry_date, status)
VALUES (1, 'GS-9002', CURRENT_DATE - 400, CURRENT_DATE - 5, 'ACTIVE')
RETURNING card_no, expiry_date, status;                          -- ... trigger stored EXPIRED

-- ---------------------------------------------------------------------
-- D.2 trg_validate_access_log  (BEFORE INSERT ON access_logs)
--     client sends GRANTED, but the card is INACTIVE (blocked in C.2) ...
-- ---------------------------------------------------------------------
INSERT INTO access_logs (card_id, gate_id, access_result)
VALUES ((SELECT card_id FROM cards WHERE card_no = 'GS-9001'), 1, 'GRANTED')
RETURNING scan_id, card_id, gate_id, access_result;              -- ... trigger stored DENIED

-- a scan at a gate under MAINTENANCE is denied too
INSERT INTO access_logs (card_id, gate_id)
VALUES (1, (SELECT gate_id FROM gates WHERE status = 'MAINTENANCE' LIMIT 1))
RETURNING scan_id, gate_id, access_result;                       -- DENIED

-- a valid card at an ACTIVE gate stays GRANTED
INSERT INTO access_logs (card_id, gate_id) VALUES (1, 1)
RETURNING scan_id, access_result;                                -- GRANTED

-- ---------------------------------------------------------------------
-- D.3 trg_validate_incident_time  (BEFORE INSERT/UPDATE ON incidents)
--     an incident cannot be detected BEFORE its scan (cross-table rule)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    INSERT INTO incidents (scan_id, detected_time)
    VALUES (1, (SELECT scan_time - INTERVAL '1 hour' FROM access_logs WHERE scan_id = 1));
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'trg_validate_incident_time rejected the row: %', SQLERRM;
END $$;

-- ---------------------------------------------------------------------
-- D.4 trg_employee_requires_card  (deferred CONSTRAINT TRIGGER ON employees)
--     total participation: an employee without any card is rejected
-- ---------------------------------------------------------------------
DO $$
BEGIN
    INSERT INTO employees (name, department, phone) VALUES ('No Card Person', 'HR', '9000000002');
    SET CONSTRAINTS trg_employee_requires_card IMMEDIATE;          -- check now instead of at COMMIT
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'trg_employee_requires_card rejected the row: %', SQLERRM;
END $$;
SET CONSTRAINTS ALL DEFERRED;

-- ---------------------------------------------------------------------
-- D.5 trg_card_removal_keeps_one  (deferred CONSTRAINT TRIGGER ON cards)
--     the LAST card of an employee cannot be deleted
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_emp INT;
BEGIN
    CALL sp_add_employee_with_card('One Card Person', 'HR', '9000000003', 'GS-9003', CURRENT_DATE + 90, v_emp);
    DELETE FROM cards WHERE card_no = 'GS-9003';
    SET CONSTRAINTS trg_card_removal_keeps_one IMMEDIATE;
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'trg_card_removal_keeps_one rejected the delete: %', SQLERRM;
END $$;
SET CONSTRAINTS ALL DEFERRED;


-- =====================================================================
-- E. CTE AND RECURSIVE CTE
-- =====================================================================

-- ---------------------------------------------------------------------
-- E.1 CTE (two named sub-queries): open incidents per employee
-- ---------------------------------------------------------------------
WITH open_incidents AS (
    SELECT i.incident_id, a.card_id
    FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id
    WHERE i.status IN ('OPEN', 'INVESTIGATING')
),
per_employee AS (
    SELECT c.emp_id, COUNT(*) AS open_cnt
    FROM open_incidents o JOIN cards c ON c.card_id = o.card_id
    GROUP BY c.emp_id
)
SELECT e.name, e.department, p.open_cnt
FROM per_employee p JOIN employees e ON e.emp_id = p.emp_id
ORDER BY p.open_cnt DESC, e.name;

-- ---------------------------------------------------------------------
-- E.2 RECURSIVE CTE: 14-day calendar (days with 0 incidents still appear)
-- ---------------------------------------------------------------------
WITH RECURSIVE days(day) AS (
    SELECT CURRENT_DATE - 13                    -- anchor member
    UNION ALL
    SELECT day + 1 FROM days                    -- recursive member
    WHERE day < CURRENT_DATE                    -- stop condition
)
SELECT d.day, COUNT(i.incident_id) AS incidents
FROM days d
LEFT JOIN incidents i ON i.detected_time::date = d.day
GROUP BY d.day
ORDER BY d.day;

-- ---------------------------------------------------------------------
-- E.3 RECURSIVE CTE: tailgating "burst chains" - scans at the same gate
--     that follow each other within 10 seconds are linked into one chain
-- ---------------------------------------------------------------------
WITH RECURSIVE ordered AS (
    SELECT scan_id, gate_id, scan_time,
           LAG(scan_time) OVER (PARTITION BY gate_id ORDER BY scan_time, scan_id) AS prev_time,
           LAG(scan_id)   OVER (PARTITION BY gate_id ORDER BY scan_time, scan_id) AS prev_id
    FROM access_logs
),
chain AS (
    SELECT scan_id AS chain_start, scan_id, gate_id, scan_time, 1 AS depth
    FROM ordered
    WHERE prev_time IS NULL OR scan_time - prev_time > INTERVAL '10 seconds'
    UNION ALL
    SELECT ch.chain_start, o.scan_id, o.gate_id, o.scan_time, ch.depth + 1
    FROM chain ch
    JOIN ordered o ON o.gate_id = ch.gate_id
                  AND o.prev_id = ch.scan_id   -- link by id: no loops on equal times
                  AND o.scan_time - ch.scan_time <= INTERVAL '10 seconds'
)
SELECT chain_start, gate_id, COUNT(*) AS scans_in_chain,
       MIN(scan_time) AS started, MAX(scan_time) AS ended
FROM chain
GROUP BY chain_start, gate_id
HAVING COUNT(*) > 1;


-- =====================================================================
-- F. BONUS: VIEW, WINDOW FUNCTIONS, SAVEPOINT
-- =====================================================================

-- F.1 VIEW - a saved query over the 5-table join (created inside this transaction only)
CREATE VIEW vw_incident_details AS
SELECT i.incident_id, i.severity, i.status, i.detected_time,
       g.gate_name, e.name AS card_holder, c.card_no
FROM incidents i
JOIN access_logs a ON a.scan_id = i.scan_id
JOIN gates g       ON g.gate_id = a.gate_id
JOIN cards c       ON c.card_id = a.card_id
JOIN employees e   ON e.emp_id  = c.emp_id;

SELECT * FROM vw_incident_details WHERE severity IN ('HIGH', 'CRITICAL') ORDER BY detected_time;

-- F.2 WINDOW FUNCTIONS - rank gates by incidents, running total of scans per day
SELECT gate_name, incidents,
       RANK()       OVER (ORDER BY incidents DESC) AS risk_rank,
       ROUND(100.0 * incidents / SUM(incidents) OVER (), 1) AS pct_of_all
FROM (SELECT gate_name, COUNT(*) AS incidents FROM vw_incident_details GROUP BY gate_name) t;

SELECT scan_time::date AS day, COUNT(*) AS scans,
       SUM(COUNT(*)) OVER (ORDER BY scan_time::date) AS running_total
FROM access_logs
GROUP BY scan_time::date
ORDER BY day;

-- F.3 SAVEPOINT - undo part of a transaction
SAVEPOINT before_update;
UPDATE gates SET status = 'INACTIVE';                      -- oops: every gate
SELECT COUNT(*) AS inactive_gates FROM gates WHERE status = 'INACTIVE';
ROLLBACK TO SAVEPOINT before_update;                       -- undo just that update
SELECT COUNT(*) AS inactive_gates_after_rollback FROM gates WHERE status = 'INACTIVE';


-- =====================================================================
-- Undo everything this demo did (new incident, employees, cards, scans, view)
-- =====================================================================
ROLLBACK;
