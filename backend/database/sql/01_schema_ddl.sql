-- ============================================================================
-- GATESENTRY DATABASE DEFINITION (DDL)
-- Project: GateSentry - Explainable Office Tailgating Detection System
-- Target DBMS: PostgreSQL 14+
-- ============================================================================

-- Enable pgcrypto for UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop tables in reverse dependency order if reconstructing
DROP VIEW IF EXISTS v_incident_investigation_summary CASCADE;
DROP VIEW IF EXISTS v_high_risk_gates CASCADE;
DROP VIEW IF EXISTS v_daily_gate_traffic CASCADE;

DROP TABLE IF EXISTS detection_rules CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS evidence_assets CASCADE;
DROP TABLE IF EXISTS incident_actions CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;
DROP TABLE IF EXISTS camera_observations CASCADE;
DROP TABLE IF EXISTS gate_sessions CASCADE;
DROP TABLE IF EXISTS access_events CASCADE;
DROP TABLE IF EXISTS access_credentials CASCADE;
DROP TABLE IF EXISTS cameras CASCADE;
DROP TABLE IF EXISTS gates CASCADE;
DROP TABLE IF EXISTS zones CASCADE;
DROP TABLE IF EXISTS sites CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. USERS TABLE (System Authentication & Authorization)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('ADMIN', 'SECURITY_OFFICER', 'AUDITOR')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. EMPLOYEES TABLE (Office Personnel)
CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_code VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    department VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. SITES TABLE (Physical Campuses)
CREATE TABLE sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_name VARCHAR(255) NOT NULL UNIQUE,
    address TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. ZONES TABLE (Hierarchical Building Areas)
CREATE TABLE zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    parent_zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    zone_name VARCHAR(255) NOT NULL,
    zone_type VARCHAR(100) NOT NULL,
    sensitivity_level INT NOT NULL DEFAULT 5 CHECK (sensitivity_level >= 1 AND sensitivity_level <= 50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. GATES TABLE (Physical Portals & Access Points)
CREATE TABLE gates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    gate_code VARCHAR(50) NOT NULL UNIQUE,
    gate_name VARCHAR(255) NOT NULL,
    direction VARCHAR(20) NOT NULL DEFAULT 'ENTRY' CHECK (direction IN ('ENTRY', 'EXIT', 'BIDIRECTIONAL')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    session_window_seconds INT NOT NULL DEFAULT 8 CHECK (session_window_seconds BETWEEN 3 AND 60),
    minimum_detection_confidence FLOAT NOT NULL DEFAULT 0.65 CHECK (minimum_detection_confidence >= 0.1 AND minimum_detection_confidence <= 1.0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. CAMERAS TABLE (Optical Person-Tracking Sensors)
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL REFERENCES gates(id) ON DELETE CASCADE,
    camera_code VARCHAR(50) NOT NULL UNIQUE,
    camera_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'MAINTENANCE', 'OFFLINE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. ACCESS_CREDENTIALS TABLE (Hashed RFID/NFC/Biometric Badges)
CREATE TABLE access_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    credential_hash VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'REVOKED', 'SUSPENDED', 'EXPIRED')),
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_cred_validity_window CHECK (valid_until IS NULL OR valid_until > valid_from)
);

-- 8. ACCESS_EVENTS TABLE (Access-Control Reader Logs)
CREATE TABLE access_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL REFERENCES gates(id) ON DELETE CASCADE,
    credential_id UUID REFERENCES access_credentials(id) ON DELETE SET NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    direction VARCHAR(20) NOT NULL DEFAULT 'ENTRY' CHECK (direction IN ('ENTRY', 'EXIT')),
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('GRANTED', 'DENIED')),
    denial_reason VARCHAR(255),
    external_event_id VARCHAR(100) UNIQUE
);

-- 9. GATE_SESSIONS TABLE (Temporal Association Windows)
CREATE TABLE gate_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL REFERENCES gates(id) ON DELETE CASCADE,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closes_at TIMESTAMPTZ NOT NULL,
    expected_authorized_entries INT NOT NULL DEFAULT 0 CHECK (expected_authorized_entries >= 0),
    observed_crossings INT NOT NULL DEFAULT 0 CHECK (observed_crossings >= 0),
    unmatched_crossings INT NOT NULL DEFAULT 0 CHECK (unmatched_crossings >= 0),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'FINALIZED', 'CANCELLED')),
    finalized_at TIMESTAMPTZ,
    CONSTRAINT chk_session_times CHECK (closes_at >= opened_at)
);

-- 10. CAMERA_OBSERVATIONS TABLE (CV Tracker Crossing Events)
CREATE TABLE camera_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL REFERENCES gates(id) ON DELETE CASCADE,
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    gate_session_id UUID REFERENCES gate_sessions(id) ON DELETE SET NULL,
    tracker_id VARCHAR(100) NOT NULL, -- Anonymous tracker ID from ByteTrack
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    direction VARCHAR(20) NOT NULL DEFAULT 'ENTRY' CHECK (direction IN ('ENTRY', 'EXIT')),
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence_reference VARCHAR(255),
    external_event_id VARCHAR(100) UNIQUE
);

-- 11. INCIDENTS TABLE (Security Flagged Discrepancies)
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL REFERENCES gates(id) ON DELETE CASCADE,
    gate_session_id UUID REFERENCES gate_sessions(id) ON DELETE SET NULL,
    incident_type VARCHAR(50) NOT NULL CHECK (incident_type IN ('TAILGATING', 'UNAUTHORIZED_ENTRY', 'REPEATED_PASSBACK', 'SUSPICIOUS_LOITERING')),
    authorized_count INT NOT NULL CHECK (authorized_count >= 0),
    observed_count INT NOT NULL CHECK (observed_count >= 0),
    unmatched_count INT NOT NULL CHECK (unmatched_count >= 0),
    average_confidence FLOAT NOT NULL CHECK (average_confidence >= 0.0 AND average_confidence <= 1.0),
    risk_score FLOAT NOT NULL CHECK (risk_score >= 0.0 AND risk_score <= 100.0),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status VARCHAR(50) NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW', 'ACKNOWLEDGED', 'UNDER_INVESTIGATION', 'RESOLVED', 'FALSE_POSITIVE')),
    summary TEXT NOT NULL,
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_incidents_gate_session UNIQUE (gate_session_id)
);

-- 12. INCIDENT_ACTIONS TABLE (Investigation History Audit Trail)
CREATE TABLE incident_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('ACKNOWLEDGE', 'ASSIGN', 'NOTE', 'STATUS_CHANGE', 'RESOLVE', 'FALSE_POSITIVE')),
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 13. EVIDENCE_ASSETS TABLE (Privacy-Preserved Image/Video References)
CREATE TABLE evidence_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    object_reference VARCHAR(255) NOT NULL,
    media_type VARCHAR(50) NOT NULL DEFAULT 'IMAGE_CROPPED',
    checksum VARCHAR(64) NOT NULL,
    is_redacted BOOLEAN NOT NULL DEFAULT TRUE,
    retention_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 14. AUDIT_LOGS TABLE (Immutable System Change Audit Log)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 15. DETECTION_RULES TABLE (Configurable Gate-Specific Risk & Policy Rules)
CREATE TABLE detection_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID REFERENCES gates(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    confidence_threshold FLOAT NOT NULL DEFAULT 0.65 CHECK (confidence_threshold >= 0.1 AND confidence_threshold <= 1.0),
    session_window_seconds INT NOT NULL DEFAULT 8 CHECK (session_window_seconds BETWEEN 3 AND 60),
    zone_sensitivity_bonus INT NOT NULL DEFAULT 15 CHECK (zone_sensitivity_bonus >= 0 AND zone_sensitivity_bonus <= 50),
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 16. INCIDENT_VECTOR_OUTBOX (Reliable PostgreSQL-to-Qdrant delivery)
CREATE TABLE incident_vector_outbox (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    event_type VARCHAR(80) NOT NULL DEFAULT 'INCIDENT_CREATED',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    attempt_count INT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    last_error TEXT
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Incidents indexes (filter by status, severity, date, gate)
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_severity ON incidents(severity);
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);
CREATE INDEX idx_incidents_gate_id ON incidents(gate_id);
CREATE INDEX idx_incidents_assigned_to ON incidents(assigned_to);
CREATE INDEX idx_incidents_risk_composite ON incidents(severity, risk_score DESC);

-- Access events indexes
CREATE INDEX idx_access_events_gate_time ON access_events(gate_id, event_timestamp DESC);
CREATE INDEX idx_access_events_credential ON access_events(credential_id);
CREATE INDEX idx_access_events_decision ON access_events(decision);

-- Gate sessions indexes
CREATE INDEX idx_gate_sessions_gate_status ON gate_sessions(gate_id, status);
CREATE INDEX idx_gate_sessions_window ON gate_sessions(opened_at, closes_at);

-- Camera observations indexes
CREATE INDEX idx_camera_obs_session ON camera_observations(gate_session_id);
CREATE INDEX idx_camera_obs_gate_time ON camera_observations(gate_id, observed_at DESC);
CREATE INDEX idx_camera_obs_tracker ON camera_observations(tracker_id);

-- Zone hierarchy index
CREATE INDEX idx_zones_parent ON zones(parent_zone_id);

-- Audit logs index
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_occurred ON audit_logs(occurred_at DESC);
CREATE INDEX idx_incident_vector_outbox_ready
    ON incident_vector_outbox(status, next_attempt_at, created_at);
CREATE INDEX idx_incident_vector_outbox_incident_event
    ON incident_vector_outbox(incident_id, event_type);

-- ============================================================================
-- VIEWS FOR REPORTING & ANALYTICS
-- ============================================================================

-- View: Incident Investigation Summary
CREATE OR REPLACE VIEW v_incident_investigation_summary AS
SELECT 
    i.id AS incident_id,
    i.incident_type,
    i.severity,
    i.risk_score,
    i.status,
    i.authorized_count,
    i.observed_count,
    i.unmatched_count,
    i.created_at AS incident_time,
    g.gate_code,
    g.gate_name,
    z.zone_name,
    s.site_name,
    u.full_name AS assigned_officer,
    COUNT(ia.id) AS action_count
FROM incidents i
JOIN gates g ON i.gate_id = g.id
JOIN zones z ON g.zone_id = z.id
JOIN sites s ON z.site_id = s.id
LEFT JOIN users u ON i.assigned_to = u.id
LEFT JOIN incident_actions ia ON i.id = ia.incident_id
GROUP BY i.id, g.gate_code, g.gate_name, z.zone_name, s.site_name, u.full_name;

-- View: High Risk Gates
CREATE OR REPLACE VIEW v_high_risk_gates AS
SELECT 
    g.id AS gate_id,
    g.gate_code,
    g.gate_name,
    s.site_name,
    z.zone_name,
    COUNT(i.id) AS total_incidents,
    ROUND(AVG(i.risk_score)::NUMERIC, 2) AS avg_risk_score,
    COUNT(CASE WHEN i.severity IN ('HIGH', 'CRITICAL') THEN 1 END) AS critical_high_count
FROM gates g
JOIN zones z ON g.zone_id = z.id
JOIN sites s ON z.site_id = s.id
LEFT JOIN incidents i ON g.id = i.gate_id
GROUP BY g.id, g.gate_code, g.gate_name, s.site_name, z.zone_name;

-- View: Daily Gate Traffic Overview
CREATE OR REPLACE VIEW v_daily_gate_traffic AS
SELECT 
    DATE_TRUNC('day', ae.event_timestamp) AS traffic_date,
    g.id AS gate_id,
    g.gate_name,
    COUNT(ae.id) AS total_access_attempts,
    COUNT(CASE WHEN ae.decision = 'GRANTED' THEN 1 END) AS granted_attempts,
    COUNT(CASE WHEN ae.decision = 'DENIED' THEN 1 END) AS denied_attempts
FROM access_events ae
JOIN gates g ON ae.gate_id = g.id
GROUP BY DATE_TRUNC('day', ae.event_timestamp), g.id, g.gate_name;
