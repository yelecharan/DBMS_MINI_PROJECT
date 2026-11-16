-- ==========================================
-- TAILGATING DETECTION AND ACCESS CONTROL
-- SAMPLE DATA
-- ==========================================

BEGIN;

-- Enable pgcrypto for securely hashing demo passwords
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ==========================================
-- 1. EMPLOYEES
-- ==========================================

INSERT INTO employees
(employee_id, full_name, email, department, designation, status)
VALUES
(1, 'Rahul Sharma', 'rahul@company.com', 'IT', 'Software Engineer', 'Active'),
(2, 'Priya Reddy', 'priya@company.com', 'HR', 'HR Manager', 'Active'),
(3, 'Arjun Kumar', 'arjun@company.com', 'Finance', 'Accountant', 'Active'),
(4, 'Sneha Rao', 'sneha@company.com', 'IT', 'System Administrator', 'Active'),
(5, 'Kiran Patel', 'kiran@company.com', 'Security', 'Security Supervisor', 'Inactive')
ON CONFLICT DO NOTHING;


-- ==========================================
-- 2. ACCESS CARDS
-- ==========================================

INSERT INTO access_cards
(card_id, employee_id, card_number, card_status)
VALUES
(1, 1, 'CARD1001', 'Active'),
(2, 2, 'CARD1002', 'Active'),
(3, 3, 'CARD1003', 'Active'),
(4, 4, 'CARD1004', 'Blocked'),
(5, 5, 'CARD1005', 'Expired')
ON CONFLICT DO NOTHING;


-- ==========================================
-- 3. USERS
-- ==========================================

INSERT INTO users
(user_id, username, password_hash, role)
VALUES
(1, 'admin', crypt('Admin@123', gen_salt('bf')), 'Admin'),
(2, 'security1', crypt('Security@123', gen_salt('bf')), 'Security Officer'),
(3, 'security2', crypt('Security@456', gen_salt('bf')), 'Security Officer')
ON CONFLICT DO NOTHING;


-- ==========================================
-- 4. ACCESS LOGS
-- ==========================================

INSERT INTO access_logs
(log_id, card_id, access_time, access_type, access_result, location)
VALUES
(1, 1, '2026-10-28 09:00:00', 'Entry', 'Granted', 'Main Gate'),
(2, 1, '2026-10-28 17:30:00', 'Exit', 'Granted', 'Main Gate'),
(3, 2, '2026-10-28 09:15:00', 'Entry', 'Granted', 'Main Gate'),
(4, 3, '2026-10-28 09:30:00', 'Entry', 'Granted', 'Main Gate'),
(5, 4, '2026-10-28 10:00:00', 'Entry', 'Denied', 'Main Gate'),
(6, 5, '2026-10-28 10:15:00', 'Entry', 'Denied', 'Side Gate'),
(7, 2, '2026-10-28 18:00:00', 'Exit', 'Granted', 'Main Gate'),
(8, 3, '2026-10-29 09:20:00', 'Entry', 'Granted', 'Side Gate'),
(9, 1, '2026-10-29 09:45:00', 'Entry', 'Granted', 'Main Gate'),
(10, 4, '2026-10-29 10:30:00', 'Entry', 'Denied', 'Main Gate')
ON CONFLICT DO NOTHING;


-- ==========================================
-- 5. TAILGATING INCIDENTS
-- ==========================================

INSERT INTO tailgating_incidents
(incident_id, log_id, investigated_by, incident_time,
 description, severity, incident_status)
VALUES
(1, 3, 2, '2026-10-28 09:16:00',
 'Possible unauthorized person entered behind an authorized employee.',
 'High', 'Investigating'),

(2, 5, 2, '2026-10-28 10:02:00',
 'Blocked access card was used at the main entrance.',
 'Medium', 'Open'),

(3, 6, 3, '2026-10-28 10:17:00',
 'Expired access card attempted entry through the side gate.',
 'Low', 'Resolved'),

(4, 9, 2, '2026-10-29 09:47:00',
 'Suspicious entry activity reported near the main gate.',
 'High', 'Open')
ON CONFLICT DO NOTHING;


-- ==========================================
-- RESET SERIAL SEQUENCES
-- ==========================================

SELECT setval(pg_get_serial_sequence('employees', 'employee_id'),
              COALESCE(MAX(employee_id), 1), true)
FROM employees;

SELECT setval(pg_get_serial_sequence('access_cards', 'card_id'),
              COALESCE(MAX(card_id), 1), true)
FROM access_cards;

SELECT setval(pg_get_serial_sequence('users', 'user_id'),
              COALESCE(MAX(user_id), 1), true)
FROM users;

SELECT setval(pg_get_serial_sequence('access_logs', 'log_id'),
              COALESCE(MAX(log_id), 1), true)
FROM access_logs;

SELECT setval(pg_get_serial_sequence('tailgating_incidents', 'incident_id'),
              COALESCE(MAX(incident_id), 1), true)
FROM tailgating_incidents;


COMMIT;

-- ==========================================
-- END OF SAMPLE DATA
-- ==========================================