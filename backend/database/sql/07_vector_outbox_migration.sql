-- Additive migration for existing GateSentry PostgreSQL databases.
-- Back up the database before applying. This script does not drop application data.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_incidents_gate_session'
          AND conrelid = 'incidents'::regclass
    ) THEN
        IF EXISTS (
            SELECT gate_session_id
            FROM incidents
            WHERE gate_session_id IS NOT NULL
            GROUP BY gate_session_id
            HAVING COUNT(*) > 1
        ) THEN
            RAISE EXCEPTION
                'Cannot add one-incident-per-session constraint: duplicate gate_session_id values exist';
        END IF;
        ALTER TABLE incidents
            ADD CONSTRAINT uq_incidents_gate_session UNIQUE (gate_session_id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS incident_vector_outbox (
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

CREATE INDEX IF NOT EXISTS idx_incident_vector_outbox_ready
    ON incident_vector_outbox(status, next_attempt_at, created_at);
CREATE INDEX IF NOT EXISTS idx_incident_vector_outbox_incident_event
    ON incident_vector_outbox(incident_id, event_type);

DROP FUNCTION IF EXISTS append_audit_log(UUID, TEXT, TEXT, TEXT, JSONB, JSONB);
CREATE FUNCTION append_audit_log(
    p_actor_user_id UUID,
    p_entity_type TEXT,
    p_entity_id TEXT,
    p_action TEXT,
    p_old_values JSONB,
    p_new_values JSONB
) RETURNS SETOF public.audit_logs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO public.audit_logs (
        actor_user_id, entity_type, entity_id, action,
        old_values, new_values, occurred_at
    ) VALUES (
        p_actor_user_id, p_entity_type, p_entity_id, p_action,
        p_old_values, p_new_values, CURRENT_TIMESTAMP
    )
    RETURNING *;
END;
$$;

REVOKE ALL ON FUNCTION append_audit_log(UUID, TEXT, TEXT, TEXT, JSONB, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION append_audit_log(UUID, TEXT, TEXT, TEXT, JSONB, JSONB) TO gg_audit_writer;

DROP FUNCTION IF EXISTS enqueue_incident_vector_event(UUID, TEXT, JSONB);
CREATE FUNCTION enqueue_incident_vector_event(
    p_incident_id UUID,
    p_event_type TEXT,
    p_payload JSONB
) RETURNS SETOF public.incident_vector_outbox
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO public.incident_vector_outbox (
        incident_id, event_type, status, payload
    ) VALUES (
        p_incident_id, p_event_type, 'PENDING', p_payload
    )
    RETURNING *;
END;
$$;

REVOKE ALL ON FUNCTION enqueue_incident_vector_event(UUID, TEXT, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION enqueue_incident_vector_event(UUID, TEXT, JSONB) TO gg_admin, gg_security;

ALTER PROCEDURE finalize_gate_session(UUID) SECURITY DEFINER;
ALTER PROCEDURE finalize_gate_session(UUID) SET search_path TO pg_catalog, public;
REVOKE ALL ON PROCEDURE finalize_gate_session(UUID) FROM PUBLIC;
GRANT EXECUTE ON PROCEDURE finalize_gate_session(UUID) TO gg_admin, gg_security;
