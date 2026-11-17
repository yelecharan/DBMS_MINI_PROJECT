-- =====================================================================
-- GateSentry - 03_roles.sql : database-level role-based access control
--
--   gs_admin     (NOLOGIN group) - full DML on all five tables, can call procedures
--   gs_security  (NOLOGIN group) - read-only on master data, may record scans,
--                                  raise incidents and change ONLY incidents.status
--
-- Login roles (created by backend/scripts/init_db.py, passwords from .env):
--   admin           -> member of gs_admin
--   guard           -> member of gs_security
--   gatesentry_app  -> the FastAPI connection. It owns no privileges itself
--                      (NOINHERIT) and must run  SET LOCAL ROLE gs_admin|gs_security
--                      inside every transaction, so PostgreSQL itself enforces the
--                      role of the logged-in user.
-- Passwords are stored by PostgreSQL as SCRAM-SHA-256 hashes (never plaintext).
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gs_admin') THEN
        CREATE ROLE gs_admin NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gs_security') THEN
        CREATE ROLE gs_security NOLOGIN;
    END IF;
END $$;

-- start from a clean slate
REVOKE ALL ON employees, cards, gates, access_logs, incidents FROM PUBLIC, gs_admin, gs_security;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, gs_admin, gs_security;
REVOKE EXECUTE ON ALL FUNCTIONS  IN SCHEMA public FROM PUBLIC;
REVOKE EXECUTE ON ALL PROCEDURES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO gs_admin, gs_security;

-- ---------------- Admin: everything ----------------
GRANT SELECT, INSERT, UPDATE, DELETE
      ON employees, cards, gates, access_logs, incidents TO gs_admin;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO gs_admin;
GRANT EXECUTE ON ALL FUNCTIONS  IN SCHEMA public TO gs_admin;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA public TO gs_admin;

-- ---------------- Security staff ----------------
GRANT SELECT ON employees, cards, gates, access_logs, incidents TO gs_security;
GRANT INSERT ON access_logs TO gs_security;                 -- record card scans
GRANT INSERT ON incidents   TO gs_security;                 -- raise suspected tailgating
GRANT UPDATE (status) ON incidents TO gs_security;          -- column-level privilege
GRANT USAGE ON SEQUENCE access_logs_scan_id_seq, incidents_incident_id_seq TO gs_security;
GRANT EXECUTE ON FUNCTION
      fn_authorized_count(INT, INT),
      fn_compute_severity(INT, INT),
      fn_report_tailgating(INT, INT, INT),
      fn_gate_risk_summary(),
      fn_validate_access_log(),
      fn_validate_incident_time()
      TO gs_security;
-- trigger functions must be executable by whoever fires the trigger
GRANT EXECUTE ON FUNCTION fn_check_employee_has_card(), fn_card_auto_expire() TO gs_admin;
-- NOTE: security staff get NO DELETE anywhere and NO access to the procedures.
