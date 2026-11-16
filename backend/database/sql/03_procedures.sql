-- ============================================================================
-- GATESENTRY STORED PROCEDURES
-- Project: GateSentry - Explainable Office Tailgating Detection System
-- Target DBMS: PostgreSQL 14+
-- ============================================================================

-- Stored Procedure: Finalize Gate Session & Correlate Discrepancies
-- Executes in an atomic transaction to ensure zero partial incident records.
CREATE OR REPLACE PROCEDURE finalize_gate_session(
    p_session_id UUID
) AS $$
DECLARE
    v_session RECORD;
    v_gate RECORD;
    v_auth_count INT := 0;
    v_obs_count INT := 0;
    v_unmatched_count INT := 0;
    v_avg_confidence FLOAT := 0.0;
    v_risk_score FLOAT := 0.0;
    v_severity VARCHAR(20) := 'LOW';
    v_incident_type VARCHAR(50);
    v_summary TEXT;
    v_new_incident_id UUID;
    v_repeat_count INT := 0;
    v_zone_sensitivity INT := 5;
BEGIN
    -- 1. Verify session exists and is currently OPEN
    SELECT * INTO v_session
    FROM gate_sessions
    WHERE id = p_session_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Gate session with ID % not found', p_session_id;
    END IF;

    IF v_session.status <> 'OPEN' THEN
        RAISE NOTICE 'Gate session % is already finalized or cancelled (status: %)', p_session_id, v_session.status;
        RETURN;
    END IF;

    -- 2. Fetch gate details and zone sensitivity
    SELECT g.*, z.sensitivity_level, s.site_name INTO v_gate
    FROM gates g
    JOIN zones z ON g.zone_id = z.id
    JOIN sites s ON z.site_id = s.id
    WHERE g.id = v_session.gate_id;

    v_zone_sensitivity := COALESCE(v_gate.sensitivity_level, 5);

    -- 3. Calculate authorized entry count from access events in the session window
    SELECT COUNT(*) INTO v_auth_count
    FROM access_events
    WHERE gate_id = v_session.gate_id
      AND decision = 'GRANTED'
      AND direction = 'ENTRY'
      AND event_timestamp BETWEEN v_session.opened_at AND v_session.closes_at;

    -- 4. Calculate observed crossings count (distinct tracker IDs above confidence threshold)
    SELECT 
        COUNT(DISTINCT tracker_id),
        COALESCE(AVG(confidence), 0.0)
    INTO v_obs_count, v_avg_confidence
    FROM camera_observations
    WHERE gate_id = v_session.gate_id
      AND direction = 'ENTRY'
      AND confidence >= v_gate.minimum_detection_confidence
      AND observed_at BETWEEN v_session.opened_at AND v_session.closes_at;

    -- 5. Calculate unmatched count
    IF v_obs_count > v_auth_count THEN
        v_unmatched_count := v_obs_count - v_auth_count;
    ELSE
        v_unmatched_count := 0;
    END IF;

    -- 6. Check for repeat incidents at this gate within the last 24 hours
    SELECT COUNT(*) INTO v_repeat_count
    FROM incidents
    WHERE gate_id = v_session.gate_id
      AND created_at >= (CURRENT_TIMESTAMP - INTERVAL '24 hours');

    -- 7. Update the session record with correlated metrics
    UPDATE gate_sessions
    SET expected_authorized_entries = v_auth_count,
        observed_crossings = v_obs_count,
        unmatched_crossings = v_unmatched_count,
        status = 'FINALIZED',
        finalized_at = CURRENT_TIMESTAMP
    WHERE id = p_session_id;

    -- 8. If an anomaly is detected, generate the incident
    IF v_unmatched_count > 0 THEN
        IF v_auth_count = 0 THEN
            v_incident_type := 'UNAUTHORIZED_ENTRY';
            v_summary := FORMAT(
                'Unauthorized entry detected at %s. %s individual(s) crossed without any valid badge authorization.',
                v_gate.gate_name, v_obs_count
            );
        ELSE
            v_incident_type := 'TAILGATING';
            v_summary := FORMAT(
                'Tailgating detected at %s. Observed %s person crossings following %s valid authorization(s). %s crossing(s) were unmatched.',
                v_gate.gate_name, v_obs_count, v_auth_count, v_unmatched_count
            );
        END IF;

        -- Calculate explainable risk score using our dedicated function
        v_risk_score := calculate_incident_risk_score(
            v_unmatched_count,
            v_avg_confidence,
            v_zone_sensitivity,
            v_repeat_count
        );

        -- Map severity according to defined rubric thresholds
        IF v_risk_score >= 80.0 THEN
            v_severity := 'CRITICAL';
        ELSIF v_risk_score >= 60.0 THEN
            v_severity := 'HIGH';
        ELSIF v_risk_score >= 35.0 THEN
            v_severity := 'MEDIUM';
        ELSE
            v_severity := 'LOW';
        END IF;

        -- Insert incident
        INSERT INTO incidents (
            gate_id,
            gate_session_id,
            incident_type,
            authorized_count,
            observed_count,
            unmatched_count,
            average_confidence,
            risk_score,
            severity,
            status,
            summary,
            created_at,
            updated_at
        ) VALUES (
            v_session.gate_id,
            p_session_id,
            v_incident_type,
            v_auth_count,
            v_obs_count,
            v_unmatched_count,
            ROUND(v_avg_confidence::NUMERIC, 3)::FLOAT,
            v_risk_score,
            v_severity,
            'NEW',
            v_summary,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        ) RETURNING id INTO v_new_incident_id;

        INSERT INTO incident_vector_outbox (
            incident_id,
            event_type,
            status,
            payload
        ) VALUES (
            v_new_incident_id,
            'INCIDENT_CREATED',
            'PENDING',
            jsonb_build_object(
                'summary', v_summary,
                'metadata', jsonb_build_object(
                    'gate_name', v_gate.gate_name,
                    'site_name', v_gate.site_name,
                    'incident_type', v_incident_type,
                    'severity', v_severity,
                    'status', 'NEW',
                    'risk_score', v_risk_score,
                    'created_at', CURRENT_TIMESTAMP
                )
            )
        );

        RAISE NOTICE 'Incident % created for gate session % (Risk: %, Severity: %)', 
            v_new_incident_id, p_session_id, v_risk_score, v_severity;
    ELSE
        RAISE NOTICE 'Gate session % finalized normally with no discrepancies (Auth: %, Obs: %)', 
            p_session_id, v_auth_count, v_obs_count;
    END IF;

END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public;
REVOKE ALL ON PROCEDURE finalize_gate_session(UUID) FROM PUBLIC;

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
