-- =====================================================================
-- GateSentry - 05_queries.sql
-- DML, JOINs, nested / correlated / recursive queries, aggregates,
-- GROUP BY / HAVING, CTEs and calls to the stored routines.
-- Every query here is also exposed through the FastAPI backend
-- (see backend/app/routers/analytics.py) and shown in the UI.
-- =====================================================================

-- ======================== DML ========================================
-- INSERT: register a new employee with a card through the procedure
CALL sp_add_employee_with_card('Nikhil Bhat', 'Engineering', '9123456780', 'GS-2001', CURRENT_DATE + 365);

-- INSERT: record a card scan at the Main Lobby Gate
INSERT INTO access_logs (card_id, gate_id) VALUES (1, 1) RETURNING *;

-- SELECT with filtering + sorting
SELECT card_id, card_no, status, expiry_date
FROM cards
WHERE status = 'ACTIVE' AND expiry_date < CURRENT_DATE + 90
ORDER BY expiry_date;

-- UPDATE: put a gate under maintenance / move an incident forward
UPDATE gates     SET status = 'MAINTENANCE'   WHERE gate_name = 'Parking Exit';
UPDATE incidents SET status = 'INVESTIGATING' WHERE status = 'OPEN' AND severity = 'CRITICAL';

-- DELETE: remove a card that was reported lost and never used
DELETE FROM cards c
WHERE c.status = 'LOST'
  AND NOT EXISTS (SELECT 1 FROM access_logs a WHERE a.card_id = c.card_id);

-- ======================== JOINS ======================================
-- Q1 INNER JOIN across 4 tables: full scan history (who, which card, which gate)
SELECT a.scan_id, a.scan_time, e.name AS employee, e.department,
       c.card_no, g.gate_name, a.access_result
FROM access_logs a
JOIN cards     c ON c.card_id = a.card_id
JOIN employees e ON e.emp_id  = c.emp_id
JOIN gates     g ON g.gate_id = a.gate_id
ORDER BY a.scan_time DESC;

-- Q2 Multi-table JOIN (5 tables): incident details
SELECT i.incident_id, i.detected_time, i.severity, i.status,
       g.gate_name, e.name AS card_holder, c.card_no, a.scan_time
FROM incidents i
JOIN access_logs a ON a.scan_id = i.scan_id
JOIN gates       g ON g.gate_id = a.gate_id
JOIN cards       c ON c.card_id = a.card_id
JOIN employees   e ON e.emp_id  = c.emp_id
ORDER BY i.detected_time DESC;

-- Q3 LEFT JOIN: every gate with its scan count (gates never used show 0)
SELECT g.gate_id, g.gate_name, g.status, COUNT(a.scan_id) AS scans
FROM gates g
LEFT JOIN access_logs a ON a.gate_id = g.gate_id
GROUP BY g.gate_id, g.gate_name, g.status
ORDER BY scans DESC;

-- Q4 LEFT JOIN: cards that have never been used
SELECT c.card_no, e.name, c.status
FROM cards c
JOIN employees e        ON e.emp_id  = c.emp_id
LEFT JOIN access_logs a ON a.card_id = c.card_id
WHERE a.scan_id IS NULL;

-- ======================== NESTED QUERIES =============================
-- Q5 Nested (IN): employees whose card scans led to an incident
SELECT emp_id, name, department
FROM employees
WHERE emp_id IN (SELECT c.emp_id
                 FROM cards c
                 WHERE c.card_id IN (SELECT a.card_id
                                     FROM access_logs a
                                     WHERE a.scan_id IN (SELECT scan_id FROM incidents)));

-- Q6 Nested (scalar subquery): gates with more scans than the average gate
SELECT g.gate_name, COUNT(*) AS scans
FROM access_logs a JOIN gates g ON g.gate_id = a.gate_id
GROUP BY g.gate_name
HAVING COUNT(*) > (SELECT AVG(cnt) FROM (SELECT COUNT(*) AS cnt
                                         FROM access_logs GROUP BY gate_id) t);

-- ======================== CORRELATED QUERIES =========================
-- Q7 Correlated: each employee's latest scan
SELECT e.name, g.gate_name, a.scan_time
FROM access_logs a
JOIN cards c     ON c.card_id = a.card_id
JOIN employees e ON e.emp_id  = c.emp_id
JOIN gates g     ON g.gate_id = a.gate_id
WHERE a.scan_time = (SELECT MAX(a2.scan_time)
                     FROM access_logs a2 JOIN cards c2 ON c2.card_id = a2.card_id
                     WHERE c2.emp_id = e.emp_id);

-- Q8 Correlated (EXISTS): scans with another GRANTED scan at the same gate
-- within 10 seconds -> possible "piggy-back" bursts
SELECT a.scan_id, a.gate_id, a.scan_time
FROM access_logs a
WHERE EXISTS (SELECT 1 FROM access_logs b
              WHERE b.gate_id = a.gate_id
                AND b.scan_id <> a.scan_id
                AND b.access_result = 'GRANTED'
                AND b.scan_time BETWEEN a.scan_time - INTERVAL '10 seconds'
                                    AND a.scan_time + INTERVAL '10 seconds');

-- Q9 Correlated: employees with more scans than the average of their department
SELECT e.name, e.department,
       (SELECT COUNT(*) FROM access_logs a JOIN cards c ON c.card_id = a.card_id
        WHERE c.emp_id = e.emp_id) AS scans
FROM employees e
WHERE (SELECT COUNT(*) FROM access_logs a JOIN cards c ON c.card_id = a.card_id
       WHERE c.emp_id = e.emp_id)
    > (SELECT COUNT(*)::numeric / COUNT(DISTINCT e2.emp_id)
       FROM employees e2
       JOIN cards c2 ON c2.emp_id = e2.emp_id
       LEFT JOIN access_logs a2 ON a2.card_id = c2.card_id
       WHERE e2.department = e.department);

-- ======================== AGGREGATES / GROUP BY / HAVING =============
-- Q10 Incidents per severity
SELECT severity, COUNT(*) AS total,
       COUNT(*) FILTER (WHERE status IN ('OPEN','INVESTIGATING')) AS still_open
FROM incidents GROUP BY severity ORDER BY total DESC;

-- Q11 HAVING: high-risk gates (2 or more incidents)
SELECT g.gate_name, COUNT(i.incident_id) AS incidents
FROM gates g
JOIN access_logs a ON a.gate_id = g.gate_id
JOIN incidents   i ON i.scan_id = a.scan_id
GROUP BY g.gate_name
HAVING COUNT(i.incident_id) >= 2
ORDER BY incidents DESC;

-- Q12 Department access summary
SELECT e.department, COUNT(a.scan_id) AS scans,
       SUM(CASE WHEN a.access_result = 'DENIED' THEN 1 ELSE 0 END) AS denied,
       MIN(a.scan_time) AS first_scan, MAX(a.scan_time) AS last_scan
FROM employees e
JOIN cards c ON c.emp_id = e.emp_id
LEFT JOIN access_logs a ON a.card_id = c.card_id
GROUP BY e.department ORDER BY scans DESC;

-- ======================== CTEs =======================================
-- Q13 CTE: open incidents with the employee who is most often involved
WITH open_incidents AS (
    SELECT i.*, a.card_id, a.gate_id
    FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id
    WHERE i.status IN ('OPEN','INVESTIGATING')
),
per_employee AS (
    SELECT c.emp_id, COUNT(*) AS open_cnt
    FROM open_incidents o JOIN cards c ON c.card_id = o.card_id
    GROUP BY c.emp_id
)
SELECT e.name, e.department, p.open_cnt
FROM per_employee p JOIN employees e ON e.emp_id = p.emp_id
ORDER BY p.open_cnt DESC;

-- Q14 RECURSIVE CTE: daily incident trend for the last 14 days
-- (recursion generates the calendar so days with 0 incidents still appear)
WITH RECURSIVE days(day) AS (
    SELECT CURRENT_DATE - 13
    UNION ALL
    SELECT day + 1 FROM days WHERE day < CURRENT_DATE
)
SELECT d.day, COUNT(i.incident_id) AS incidents
FROM days d
LEFT JOIN incidents i ON i.detected_time::date = d.day
GROUP BY d.day ORDER BY d.day;

-- Q15 RECURSIVE CTE: tailgating "burst chains" - scans at the same gate that
-- follow each other within 10 seconds are linked into one chain
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
FROM chain GROUP BY chain_start, gate_id
HAVING COUNT(*) > 1;

-- ======================== STORED ROUTINES ============================
SELECT fn_authorized_count(17);                       -- authorised scans around scan 17
SELECT fn_compute_severity(5, 2);                     -- -> HIGH
SELECT fn_report_tailgating(30, 3);                   -- creates an incident, returns its id
SELECT * FROM fn_gate_risk_summary();                 -- CTE based risk table
CALL sp_deactivate_employee_cards(8, NULL);           -- block all cards of employee 8
