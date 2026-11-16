-- ============================================================================
-- GATESENTRY DATABASE TRIGGERS
-- Project: GateSentry - Explainable Office Tailgating Detection System
-- Target DBMS: PostgreSQL 14+
-- ============================================================================

-- 1. TRIGGER FUNCTION: Update timestamp on row modification
CREATE OR REPLACE FUNCTION trg_fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to incidents
DROP TRIGGER IF EXISTS trg_incidents_updated_at ON incidents;
CREATE TRIGGER trg_incidents_updated_at
BEFORE UPDATE ON incidents
FOR EACH ROW
EXECUTE FUNCTION trg_fn_set_updated_at();

-- Apply updated_at trigger to users
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION trg_fn_set_updated_at();

-- Apply updated_at trigger to detection_rules
DROP TRIGGER IF EXISTS trg_detection_rules_updated_at ON detection_rules;
CREATE TRIGGER trg_detection_rules_updated_at
BEFORE UPDATE ON detection_rules
FOR EACH ROW
EXECUTE FUNCTION trg_fn_set_updated_at();


-- 2. TRIGGER FUNCTION: Audit Logging for Incident Changes
CREATE OR REPLACE FUNCTION trg_fn_audit_incident_changes()
RETURNS TRIGGER AS $$
DECLARE
    v_old_json JSONB;
    v_new_json JSONB;
BEGIN
    -- Record state transitions
    IF (TG_OP = 'UPDATE') THEN
        -- Only audit if meaningful fields changed
        IF (OLD.status IS DISTINCT FROM NEW.status OR
            OLD.assigned_to IS DISTINCT FROM NEW.assigned_to OR
            OLD.resolution_notes IS DISTINCT FROM NEW.resolution_notes OR
            OLD.severity IS DISTINCT FROM NEW.severity) THEN
            
            v_old_json := jsonb_build_object(
                'status', OLD.status,
                'assigned_to', OLD.assigned_to,
                'severity', OLD.severity,
                'resolution_notes', OLD.resolution_notes,
                'updated_at', OLD.updated_at
            );
            
            v_new_json := jsonb_build_object(
                'status', NEW.status,
                'assigned_to', NEW.assigned_to,
                'severity', NEW.severity,
                'resolution_notes', NEW.resolution_notes,
                'updated_at', NEW.updated_at
            );

            INSERT INTO audit_logs (
                actor_user_id,
                entity_type,
                entity_id,
                action,
                old_values,
                new_values,
                occurred_at
            ) VALUES (
                NEW.assigned_to, -- or system actor
                'INCIDENT',
                NEW.id::TEXT,
                'STATUS_UPDATE',
                v_old_json,
                v_new_json,
                CURRENT_TIMESTAMP
            );
        END IF;
    ELSIF (TG_OP = 'INSERT') THEN
        v_new_json := jsonb_build_object(
            'incident_type', NEW.incident_type,
            'severity', NEW.severity,
            'risk_score', NEW.risk_score,
            'gate_id', NEW.gate_id,
            'status', NEW.status
        );

        INSERT INTO audit_logs (
            actor_user_id,
            entity_type,
            entity_id,
            action,
            old_values,
            new_values,
            occurred_at
        ) VALUES (
            NULL,
            'INCIDENT',
            NEW.id::TEXT,
            'CREATE',
            NULL,
            v_new_json,
            CURRENT_TIMESTAMP
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp;

-- Apply Audit Log trigger to incidents
DROP TRIGGER IF EXISTS trg_audit_incidents ON incidents;
CREATE TRIGGER trg_audit_incidents
AFTER INSERT OR UPDATE ON incidents
FOR EACH ROW
EXECUTE FUNCTION trg_fn_audit_incident_changes();
