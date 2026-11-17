-- ============================================================================
-- GATESENTRY DATABASE-LEVEL ROLES & PERMISSIONS (RBAC)
-- Project: GateSentry - Explainable Office Tailgating Detection System
-- Target DBMS: PostgreSQL 14+
-- ============================================================================

-- Create roles only when absent so rerunning this grants script does not
-- invalidate memberships assigned to runtime login roles.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gg_admin') THEN
        CREATE ROLE gg_admin WITH NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gg_security') THEN
        CREATE ROLE gg_security WITH NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gg_auditor') THEN
        CREATE ROLE gg_auditor WITH NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gg_audit_writer') THEN
        CREATE ROLE gg_audit_writer WITH NOLOGIN;
    END IF;
END
$$;

-- ============================================================================
-- 2. ADMIN ROLE (gg_admin) - Full Operational & System Management
-- ============================================================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gg_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gg_admin;
GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA public TO gg_admin;

-- ============================================================================
-- 3. SECURITY OFFICER ROLE (gg_security) - Operational Incident Investigation
-- ============================================================================
-- Read-only on physical structure and access master data
GRANT SELECT ON sites, zones, gates, cameras, employees, access_credentials TO gg_security;
GRANT SELECT ON users TO gg_security;

-- Streaming logs support controlled session updates during correlation.
GRANT SELECT, INSERT ON access_events, camera_observations TO gg_security;
GRANT SELECT, INSERT, UPDATE ON gate_sessions TO gg_security;

-- Read and update permissions on incidents & investigations
GRANT SELECT, INSERT, UPDATE ON incidents, incident_actions, evidence_assets TO gg_security;

-- Read-only on audit logs and configuration
GRANT SELECT ON audit_logs, detection_rules TO gg_security;
GRANT SELECT ON v_incident_investigation_summary, v_high_risk_gates, v_daily_gate_traffic TO gg_security;

-- Security officers CANNOT delete incidents or edit audit logs
REVOKE DELETE ON incidents, incident_actions, evidence_assets, audit_logs FROM gg_security;
REVOKE INSERT, UPDATE, DELETE ON audit_logs FROM gg_security;
REVOKE INSERT, UPDATE, DELETE ON users FROM gg_security;
REVOKE ALL PRIVILEGES ON incident_vector_outbox FROM gg_security;

-- ============================================================================
-- 4. AUDITOR ROLE (gg_auditor) - Strictly Read-Only Compliance Inspection
-- ============================================================================
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gg_auditor;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO gg_auditor;

-- Explicitly ensure NO write privileges exist
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM gg_auditor;
REVOKE ALL PRIVILEGES ON incident_vector_outbox FROM gg_auditor;

-- A dedicated capability lets application handlers append immutable audit
-- rows without granting auditors or security officers direct table writes.
GRANT EXECUTE ON FUNCTION append_audit_log(UUID, TEXT, TEXT, TEXT, JSONB, JSONB) TO gg_audit_writer;
GRANT EXECUTE ON FUNCTION enqueue_incident_vector_event(UUID, TEXT, JSONB) TO gg_admin, gg_security;
GRANT EXECUTE ON PROCEDURE finalize_gate_session(UUID) TO gg_admin, gg_security;

-- ============================================================================
-- 5. RUNTIME APPLICATION USERS (Mapped to Roles)
-- ============================================================================
-- Demonstrates mapping application transactions to Postgres roles:
-- Example application connection execution:
-- SET ROLE gg_admin; / SET ROLE gg_security; / SET ROLE gg_auditor;
-- RESET ROLE;
