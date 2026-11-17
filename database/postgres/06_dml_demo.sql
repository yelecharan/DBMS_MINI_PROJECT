-- =====================================================================
-- GateSentry - 06_dml_demo.sql
-- Demo script for the viva / report:
--   1. how many tables exist           4. INSERT into every table
--   2. structure of every table        5. UPDATE and DELETE
--   3. view the data of every table    6. view the data again
--
-- HOW TO RUN (pgAdmin 4):
--   Databases -> gatesentry -> right-click -> Query Tool  (tab title must say "gatesentry/...")
--   open this file and run it all (F5), or select one block and run only that block.
-- psql:  psql -U postgres -d gatesentry -f 06_dml_demo.sql
-- The script can be run again: rows with UNIQUE values are skipped (ON CONFLICT DO NOTHING).
-- =====================================================================


-- =====================================================================
-- 1. HOW MANY TABLES ARE THERE?
-- =====================================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT COUNT(*) AS total_tables
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- number of rows in each table
SELECT 'employees'   AS table_name, COUNT(*) AS total_rows FROM employees
UNION ALL SELECT 'cards',       COUNT(*) FROM cards
UNION ALL SELECT 'gates',       COUNT(*) FROM gates
UNION ALL SELECT 'access_logs', COUNT(*) FROM access_logs
UNION ALL SELECT 'incidents',   COUNT(*) FROM incidents;


-- =====================================================================
-- 2. STRUCTURE OF EVERY TABLE (columns, data types, NULL, defaults)
-- =====================================================================
SELECT table_name, ordinal_position AS pos, column_name, data_type,
       character_maximum_length AS max_len, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('employees','cards','gates','access_logs','incidents')
ORDER BY table_name, ordinal_position;

-- all constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK)
SELECT conrelid::regclass AS table_name,
       conname            AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY'
                    WHEN 'u' THEN 'UNIQUE'      WHEN 'c' THEN 'CHECK' END AS type,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
ORDER BY 1, 3;


-- =====================================================================
-- 3. VIEW THE DATA OF EVERY TABLE
-- =====================================================================
SELECT * FROM employees   ORDER BY emp_id;
SELECT * FROM cards       ORDER BY card_id;
SELECT * FROM gates       ORDER BY gate_id;
SELECT * FROM access_logs ORDER BY scan_id;
SELECT * FROM incidents   ORDER BY incident_id;


-- =====================================================================
-- 4. INSERT INTO EVERY TABLE
-- =====================================================================

-- 4.1 employees + cards
-- Total participation: every employee must own a card, so the employee and the
-- first card are inserted in ONE transaction (the deferred trigger checks at COMMIT).
BEGIN;
INSERT INTO employees (name, department, phone)
VALUES ('Kavya Shetty', 'Research', '9988776655')
ON CONFLICT (phone) DO NOTHING;

INSERT INTO cards (emp_id, card_no, issue_date, expiry_date, status)
VALUES ((SELECT emp_id FROM employees WHERE phone = '9988776655'),
        'GS-3001', CURRENT_DATE, CURRENT_DATE + 365, 'ACTIVE')
ON CONFLICT (card_no) DO NOTHING;
COMMIT;

-- same thing using the stored procedure (employee + card in one call)
-- (wrapped in a DO block so a second run skips it instead of hitting the UNIQUE phone constraint)
DO $$
DECLARE
    v_emp_id INT;                       -- receives the INOUT parameter p_emp_id
BEGIN
    IF NOT EXISTS (SELECT 1 FROM employees WHERE phone = '9988776656') THEN
        CALL sp_add_employee_with_card('Rahul Verma', 'Finance', '9988776656', 'GS-3002',
                                       CURRENT_DATE + 365, v_emp_id);
        RAISE NOTICE 'Procedure created employee % with card GS-3002', v_emp_id;
    END IF;
END $$;

-- 4.2 a second card for an existing employee (one employee -> many cards)
INSERT INTO cards (emp_id, card_no, expiry_date)
VALUES ((SELECT emp_id FROM employees WHERE phone = '9988776655'), 'GS-3003', CURRENT_DATE + 180)
ON CONFLICT (card_no) DO NOTHING;

-- 4.3 gates (multi-row INSERT)
INSERT INTO gates (gate_name, location, type, status) VALUES
    ('Research Wing Door', 'Block D - 3rd Floor', 'BIDIRECTIONAL', 'ACTIVE'),
    ('Loading Bay',        'Block D - Ground',    'ENTRY',         'ACTIVE')
ON CONFLICT (gate_name) DO NOTHING;

-- 4.4 access_logs (card scans). Two GRANTED scans 4 seconds apart at the same gate.
-- access_result is decided by trigger trg_validate_access_log.
INSERT INTO access_logs (card_id, gate_id, scan_time)
VALUES ((SELECT card_id FROM cards WHERE card_no = 'GS-3001'),
        (SELECT gate_id FROM gates WHERE gate_name = 'Research Wing Door'),
        LOCALTIMESTAMP - INTERVAL '4 seconds'),
       ((SELECT card_id FROM cards WHERE card_no = 'GS-1006'),
        (SELECT gate_id FROM gates WHERE gate_name = 'Research Wing Door'),
        LOCALTIMESTAMP)
RETURNING scan_id, card_id, gate_id, scan_time, access_result;

-- a scan with an INACTIVE card -> the trigger stores it as DENIED
INSERT INTO access_logs (card_id, gate_id)
VALUES ((SELECT card_id FROM cards WHERE card_no = 'GS-1008'),
        (SELECT gate_id FROM gates WHERE gate_name = 'Research Wing Door'))
RETURNING scan_id, access_result;

-- 4.5 incidents
-- (a) plain INSERT
INSERT INTO incidents (scan_id, detected_time, severity, status)
VALUES ((SELECT MAX(scan_id) FROM access_logs WHERE card_id = (SELECT card_id FROM cards WHERE card_no = 'GS-3001')),
        LOCALTIMESTAMP, 'MEDIUM', 'OPEN')
RETURNING *;

-- (b) through the stored function: 5 people observed, authorised count computed by the DB
SELECT fn_report_tailgating(
         (SELECT MAX(scan_id) FROM access_logs WHERE card_id = (SELECT card_id FROM cards WHERE card_no = 'GS-1006')),
         5) AS new_incident_id;


-- =====================================================================
-- 5. UPDATE AND DELETE
-- =====================================================================
UPDATE employees SET department = 'Research & Development' WHERE phone = '9988776655';
UPDATE cards     SET status = 'LOST' WHERE card_no = 'GS-3003';
UPDATE gates     SET status = 'MAINTENANCE' WHERE gate_name = 'Loading Bay';
UPDATE incidents SET status = 'INVESTIGATING'
WHERE scan_id IN (SELECT scan_id FROM access_logs
                  WHERE gate_id = (SELECT gate_id FROM gates WHERE gate_name = 'Research Wing Door'))
  AND status = 'OPEN';

-- DELETE a row that nothing references (allowed)
DELETE FROM gates WHERE gate_name = 'Loading Bay' RETURNING *;

-- DELETE a card that has scans -> rejected by ON DELETE RESTRICT (audit trail).
-- Uncomment to see the error:
-- DELETE FROM cards WHERE card_no = 'GS-3001';


-- =====================================================================
-- 6. VIEW THE DATA AGAIN
-- =====================================================================
SELECT * FROM employees WHERE phone IN ('9988776655', '9988776656');
SELECT c.card_id, c.card_no, e.name, c.issue_date, c.expiry_date, c.status
FROM cards c JOIN employees e ON e.emp_id = c.emp_id
WHERE c.card_no LIKE 'GS-300%';
SELECT * FROM gates ORDER BY gate_id;

-- the new scans and incidents, joined with names (readable view of the data)
SELECT a.scan_id, a.scan_time, e.name AS employee, c.card_no, g.gate_name, a.access_result
FROM access_logs a
JOIN cards c     ON c.card_id = a.card_id
JOIN employees e ON e.emp_id  = c.emp_id
JOIN gates g     ON g.gate_id = a.gate_id
WHERE g.gate_name = 'Research Wing Door'
ORDER BY a.scan_id;

SELECT i.incident_id, i.scan_id, i.detected_time, i.severity, i.status, g.gate_name
FROM incidents i
JOIN access_logs a ON a.scan_id = i.scan_id
JOIN gates g       ON g.gate_id = a.gate_id
WHERE g.gate_name = 'Research Wing Door'
ORDER BY i.incident_id;

-- row counts after the inserts
SELECT 'employees'   AS table_name, COUNT(*) AS total_rows FROM employees
UNION ALL SELECT 'cards',       COUNT(*) FROM cards
UNION ALL SELECT 'gates',       COUNT(*) FROM gates
UNION ALL SELECT 'access_logs', COUNT(*) FROM access_logs
UNION ALL SELECT 'incidents',   COUNT(*) FROM incidents;

-- To go back to the original sample data:  cd backend && .venv\Scripts\python -m scripts.init_db
