-- =====================================================================
-- GateSentry - 06_dml_demo.sql
-- Demo script for the viva / report:
--   1. how many tables exist           5. view the inserted data
--   2. structure of every table        6. UPDATE (one per table)
--   3. view the data of every table    7. DELETE (one per table, child -> parent)
--   4. INSERT (one per table)
--
-- HOW TO RUN (pgAdmin 4):
--   Databases -> gatesentry -> right-click -> Query Tool  (tab title must say "gatesentry/...")
--   open this file and run it all (F5), or select one block and run only that block.
-- psql:  psql -U postgres -d gatesentry -f 06_dml_demo.sql
-- Section 7 deletes the demo rows again, so the script can be run any number of times.
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
-- (before inserting) remove demo rows left over from an earlier run, if any.
-- On a clean database these statements simply delete 0 rows.
-- =====================================================================
DELETE FROM incidents WHERE scan_id IN (
    SELECT a.scan_id FROM access_logs a
    JOIN cards c ON c.card_id = a.card_id
    JOIN gates g ON g.gate_id = a.gate_id
    WHERE c.card_no LIKE 'GS-300%' OR g.gate_name IN ('Research Wing Door', 'Loading Bay'));
DELETE FROM access_logs WHERE scan_id IN (
    SELECT a.scan_id FROM access_logs a
    JOIN cards c ON c.card_id = a.card_id
    JOIN gates g ON g.gate_id = a.gate_id
    WHERE c.card_no LIKE 'GS-300%' OR g.gate_name IN ('Research Wing Door', 'Loading Bay'));
DELETE FROM employees WHERE phone IN ('9988776655', '9988776656');
DELETE FROM gates     WHERE gate_name IN ('Research Wing Door', 'Loading Bay');


-- =====================================================================
-- 4. INSERT - ONE INSERT PER TABLE
--    Order matters: parent tables first (employees, gates), then the tables
--    that reference them (cards -> access_logs -> incidents).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 4.1 INSERT INTO employees
-- ---------------------------------------------------------------------
-- An employee must own at least one card (total participation, checked by a
-- deferred trigger at COMMIT), so 4.1 and 4.2 run inside ONE transaction.
BEGIN;

INSERT INTO employees (name, department, phone)
VALUES ('Kavya Shetty', 'Research', '9988776655')
RETURNING *;

-- ---------------------------------------------------------------------
-- 4.2 INSERT INTO cards          (FK emp_id -> employees)
-- ---------------------------------------------------------------------
INSERT INTO cards (emp_id, card_no, issue_date, expiry_date, status)
VALUES ((SELECT emp_id FROM employees WHERE phone = '9988776655'),
        'GS-3001', CURRENT_DATE, CURRENT_DATE + 365, 'ACTIVE')
RETURNING *;

COMMIT;

-- ---------------------------------------------------------------------
-- 4.3 INSERT INTO gates
-- ---------------------------------------------------------------------
INSERT INTO gates (gate_name, location, type, status)
VALUES ('Research Wing Door', 'Block D - 3rd Floor', 'BIDIRECTIONAL', 'ACTIVE')
RETURNING *;

-- ---------------------------------------------------------------------
-- 4.4 INSERT INTO access_logs    (FK card_id -> cards, FK gate_id -> gates)
-- ---------------------------------------------------------------------
-- access_result is filled in by trigger trg_validate_access_log
-- (GRANTED here because the card and the gate are both ACTIVE).
INSERT INTO access_logs (card_id, gate_id, scan_time)
VALUES ((SELECT card_id FROM cards WHERE card_no = 'GS-3001'),
        (SELECT gate_id FROM gates WHERE gate_name = 'Research Wing Door'),
        LOCALTIMESTAMP)
RETURNING *;

-- ---------------------------------------------------------------------
-- 4.5 INSERT INTO incidents      (FK scan_id -> access_logs)
-- ---------------------------------------------------------------------
INSERT INTO incidents (scan_id, detected_time, severity, status)
VALUES ((SELECT MAX(a.scan_id) FROM access_logs a
         JOIN cards c ON c.card_id = a.card_id
         WHERE c.card_no = 'GS-3001'),
        LOCALTIMESTAMP, 'HIGH', 'OPEN')
RETURNING *;


-- =====================================================================
-- 5. VIEW THE INSERTED DATA
-- =====================================================================
SELECT * FROM employees WHERE phone = '9988776655';
SELECT * FROM cards     WHERE card_no = 'GS-3001';
SELECT * FROM gates     WHERE gate_name = 'Research Wing Door';

-- the new scan and incident joined with names (readable view)
SELECT i.incident_id, i.severity, i.status, a.scan_id, a.scan_time, a.access_result,
       e.name AS employee, c.card_no, g.gate_name
FROM incidents i
JOIN access_logs a ON a.scan_id = i.scan_id
JOIN cards c       ON c.card_id = a.card_id
JOIN employees e   ON e.emp_id  = c.emp_id
JOIN gates g       ON g.gate_id = a.gate_id
WHERE c.card_no = 'GS-3001';

-- row counts after the inserts (each table has one more row)
SELECT 'employees'   AS table_name, COUNT(*) AS total_rows FROM employees
UNION ALL SELECT 'cards',       COUNT(*) FROM cards
UNION ALL SELECT 'gates',       COUNT(*) FROM gates
UNION ALL SELECT 'access_logs', COUNT(*) FROM access_logs
UNION ALL SELECT 'incidents',   COUNT(*) FROM incidents;


-- =====================================================================
-- 6. UPDATE - ONE UPDATE PER TABLE
-- =====================================================================

-- 6.1 UPDATE employees
UPDATE employees SET department = 'Research & Development'
WHERE phone = '9988776655' RETURNING *;

-- 6.2 UPDATE cards
UPDATE cards SET expiry_date = CURRENT_DATE + 730
WHERE card_no = 'GS-3001' RETURNING *;

-- 6.3 UPDATE gates
UPDATE gates SET location = 'Block D - 4th Floor'
WHERE gate_name = 'Research Wing Door' RETURNING *;

-- 6.4 UPDATE access_logs
UPDATE access_logs SET scan_time = scan_time - INTERVAL '1 minute'
WHERE card_id = (SELECT card_id FROM cards WHERE card_no = 'GS-3001') RETURNING *;

-- 6.5 UPDATE incidents
UPDATE incidents SET status = 'INVESTIGATING'
WHERE scan_id IN (SELECT a.scan_id FROM access_logs a JOIN cards c ON c.card_id = a.card_id
                  WHERE c.card_no = 'GS-3001')
RETURNING *;


-- =====================================================================
-- 7. DELETE - ONE DELETE PER TABLE (removes the demo rows again)
--    Order is the reverse of the inserts: child rows first, because the
--    foreign keys use ON DELETE RESTRICT (an access log with incidents, or a
--    card with access logs, cannot be deleted while those rows exist).
-- =====================================================================

-- 7.1 DELETE FROM incidents
DELETE FROM incidents
WHERE scan_id IN (SELECT a.scan_id FROM access_logs a JOIN cards c ON c.card_id = a.card_id
                  WHERE c.card_no = 'GS-3001')
RETURNING *;

-- 7.2 DELETE FROM access_logs
DELETE FROM access_logs
WHERE card_id = (SELECT card_id FROM cards WHERE card_no = 'GS-3001')
RETURNING *;

-- 7.3 DELETE FROM employees  (ON DELETE CASCADE also deletes the employee's card GS-3001)
DELETE FROM employees WHERE phone = '9988776655' RETURNING *;

-- 7.4 DELETE FROM cards      (already removed by the cascade above -> "DELETE 0")
DELETE FROM cards WHERE card_no = 'GS-3001' RETURNING *;

-- 7.5 DELETE FROM gates
DELETE FROM gates WHERE gate_name = 'Research Wing Door' RETURNING *;

-- row counts after the deletes (back to the starting numbers)
SELECT 'employees'   AS table_name, COUNT(*) AS total_rows FROM employees
UNION ALL SELECT 'cards',       COUNT(*) FROM cards
UNION ALL SELECT 'gates',       COUNT(*) FROM gates
UNION ALL SELECT 'access_logs', COUNT(*) FROM access_logs
UNION ALL SELECT 'incidents',   COUNT(*) FROM incidents;

-- TIP: to keep the inserted rows (e.g. to look at them in pgAdmin's table view),
--      run only sections 4 to 6 and skip section 7.
