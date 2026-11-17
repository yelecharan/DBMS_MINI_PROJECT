-- =====================================================================
-- GateSentry - 04_seed.sql : sample data (DML - INSERT)
-- Timestamps are relative to LOCALTIMESTAMP so the dashboard always shows
-- activity from the last two weeks.
-- =====================================================================
BEGIN;   -- employees + their first card in one transaction (deferred participation trigger)

INSERT INTO employees (name, department, phone) VALUES
 ('Aarav Sharma',   'Engineering', '9876543210'),
 ('Priya Nair',     'HR',          '9876543211'),
 ('Rohan Gupta',    'Finance',     '9876543212'),
 ('Sneha Reddy',    'Engineering', '9876543213'),
 ('Karthik Iyer',   'Security',    '9876543214'),
 ('Ananya Rao',     'Research',    '9876543215'),
 ('Vikram Singh',   'Operations',  '9876543216'),
 ('Meera Joshi',    'Finance',     '9876543217'),
 ('Arjun Menon',    'Research',    '9876543218'),
 ('Divya Krishnan', 'Operations',  '9876543219');

INSERT INTO cards (emp_id, card_no, issue_date, expiry_date, status) VALUES
 (1,  'GS-1001', CURRENT_DATE - 300, CURRENT_DATE + 400, 'ACTIVE'),
 (2,  'GS-1002', CURRENT_DATE - 250, CURRENT_DATE + 450, 'ACTIVE'),
 (3,  'GS-1003', CURRENT_DATE - 200, CURRENT_DATE + 500, 'ACTIVE'),
 (4,  'GS-1004', CURRENT_DATE - 180, CURRENT_DATE + 520, 'ACTIVE'),
 (5,  'GS-1005', CURRENT_DATE - 365, CURRENT_DATE + 365, 'ACTIVE'),
 (6,  'GS-1006', CURRENT_DATE - 120, CURRENT_DATE + 600, 'ACTIVE'),
 (7,  'GS-1007', CURRENT_DATE - 90,  CURRENT_DATE + 640, 'ACTIVE'),
 (8,  'GS-1008', CURRENT_DATE - 60,  CURRENT_DATE + 670, 'INACTIVE'),
 (9,  'GS-1009', CURRENT_DATE - 45,  CURRENT_DATE + 680, 'ACTIVE'),
 (10, 'GS-1010', CURRENT_DATE - 30,  CURRENT_DATE + 700, 'ACTIVE'),
 (1,  'GS-1011', CURRENT_DATE - 700, CURRENT_DATE + 30,  'LOST'),
 (6,  'GS-1012', CURRENT_DATE - 800, CURRENT_DATE - 30,  'ACTIVE');  -- trigger turns this into EXPIRED

INSERT INTO gates (gate_name, location, type, status) VALUES
 ('Main Lobby Gate', 'Block A - Ground Floor', 'ENTRY',         'ACTIVE'),
 ('R&D Lab Door',    'Block B - 2nd Floor',   'BIDIRECTIONAL', 'ACTIVE'),
 ('Server Room',     'Block B - Basement',    'ENTRY',         'ACTIVE'),
 ('Parking Exit',    'Basement Parking',      'EXIT',          'ACTIVE'),
 ('Cafeteria Gate',  'Block C - 1st Floor',   'BIDIRECTIONAL', 'MAINTENANCE');

COMMIT;

-- access_result defaults to GRANTED; trg_validate_access_log forces DENIED for
-- inactive/lost/expired cards and for gates under maintenance.
INSERT INTO access_logs (card_id, gate_id, scan_time) VALUES
 (1,  1, LOCALTIMESTAMP - INTERVAL '13 days 09:00:00'),
 (2,  1, LOCALTIMESTAMP - INTERVAL '13 days 08:59:55'),
 (3,  2, LOCALTIMESTAMP - INTERVAL '12 days 07:30:00'),
 (4,  3, LOCALTIMESTAMP - INTERVAL '12 days 05:00:00'),
 (5,  1, LOCALTIMESTAMP - INTERVAL '11 days 09:00:00'),
 (6,  2, LOCALTIMESTAMP - INTERVAL '11 days 08:00:00'),
 (8,  1, LOCALTIMESTAMP - INTERVAL '10 days 09:15:00'),
 (7,  4, LOCALTIMESTAMP - INTERVAL '10 days 01:00:00'),
 (9,  2, LOCALTIMESTAMP - INTERVAL '9 days 06:00:00'),
 (10, 3, LOCALTIMESTAMP - INTERVAL '9 days 03:00:00'),
 (1,  3, LOCALTIMESTAMP - INTERVAL '8 days 04:00:00'),
 (4,  2, LOCALTIMESTAMP - INTERVAL '7 days 05:00:00'),
 (2,  5, LOCALTIMESTAMP - INTERVAL '7 days 02:00:00'),
 (3,  1, LOCALTIMESTAMP - INTERVAL '6 days 09:00:00'),
 (12, 1, LOCALTIMESTAMP - INTERVAL '6 days 08:00:00'),
 (5,  3, LOCALTIMESTAMP - INTERVAL '5 days 07:00:00'),
 (6,  2, LOCALTIMESTAMP - INTERVAL '5 days 06:59:52'),
 (9,  2, LOCALTIMESTAMP - INTERVAL '5 days 06:59:58'),
 (7,  1, LOCALTIMESTAMP - INTERVAL '4 days 09:00:00'),
 (10, 4, LOCALTIMESTAMP - INTERVAL '4 days 01:00:00'),
 (11, 1, LOCALTIMESTAMP - INTERVAL '3 days 09:00:00'),
 (4,  3, LOCALTIMESTAMP - INTERVAL '3 days 05:00:00'),
 (1,  1, LOCALTIMESTAMP - INTERVAL '2 days 09:00:00'),
 (2,  2, LOCALTIMESTAMP - INTERVAL '2 days 07:00:00'),
 (3,  3, LOCALTIMESTAMP - INTERVAL '1 day 06:00:00'),
 (8,  3, LOCALTIMESTAMP - INTERVAL '1 day 05:00:00'),
 (5,  1, LOCALTIMESTAMP - INTERVAL '20:00:00'),
 (6,  2, LOCALTIMESTAMP - INTERVAL '10:00:00'),
 (9,  3, LOCALTIMESTAMP - INTERVAL '05:00:00'),
 (1,  1, LOCALTIMESTAMP - INTERVAL '01:00:00');

-- incidents detected 2 minutes after the related scan
INSERT INTO incidents (scan_id, detected_time, severity, status)
SELECT v.scan_id, a.scan_time + INTERVAL '2 minutes', v.severity, v.status
FROM (VALUES
        (1,  'MEDIUM',   'RESOLVED'),
        (4,  'HIGH',     'RESOLVED'),
        (7,  'LOW',      'FALSE_ALARM'),
        (11, 'HIGH',     'INVESTIGATING'),
        (17, 'LOW',      'RESOLVED'),
        (22, 'CRITICAL', 'OPEN'),
        (25, 'MEDIUM',   'OPEN'),
        (29, 'LOW',      'OPEN'),
        (11, 'LOW',      'RESOLVED')
     ) AS v(scan_id, severity, status)
JOIN access_logs a ON a.scan_id = v.scan_id
ORDER BY a.scan_time, v.severity;
