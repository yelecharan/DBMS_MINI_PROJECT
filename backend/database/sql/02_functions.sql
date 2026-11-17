-- ============================================================================
-- GATESENTRY STORED FUNCTIONS
-- Project: GateSentry - Explainable Office Tailgating Detection System
-- Target DBMS: PostgreSQL 14+
-- ============================================================================

-- Function 1: Deterministic, Explainable Risk Score Calculation
-- Implements formula:
-- Risk = (25 * unmatched_count) + (20 * avg_confidence) + zone_sensitivity_bonus + repeat_bonus
-- Clamped strictly between 0 and 100.
CREATE OR REPLACE FUNCTION calculate_incident_risk_score(
    p_unmatched_count INT,
    p_average_confidence FLOAT,
    p_zone_sensitivity INT,
    p_repeat_count INT DEFAULT 0
) RETURNS FLOAT AS $$
DECLARE
    v_raw_score FLOAT;
    v_confidence_component FLOAT;
    v_unmatched_component FLOAT;
    v_repeat_bonus FLOAT;
    v_final_score FLOAT;
BEGIN
    -- Validation
    IF p_unmatched_count < 0 THEN
        p_unmatched_count := 0;
    END IF;
    IF p_average_confidence < 0.0 THEN
        p_average_confidence := 0.0;
    ELSIF p_average_confidence > 1.0 THEN
        p_average_confidence := 1.0;
    END IF;

    -- Calculate individual components
    v_unmatched_component := 25.0 * p_unmatched_count;
    v_confidence_component := 20.0 * p_average_confidence;
    v_repeat_bonus := LEAST(15.0, 5.0 * p_repeat_count);

    -- Sum components
    v_raw_score := v_unmatched_component + v_confidence_component + p_zone_sensitivity + v_repeat_bonus;

    -- Clamp between 0.0 and 100.0
    IF v_raw_score < 0.0 THEN
        v_final_score := 0.0;
    ELSIF v_raw_score > 100.0 THEN
        v_final_score := 100.0;
    ELSE
        v_final_score := ROUND(v_raw_score::NUMERIC, 2);
    END IF;

    RETURN v_final_score;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Function 2: Aggregate Gate Incident Statistics (with parameterizable lookback)
CREATE OR REPLACE FUNCTION get_gate_incident_statistics(
    p_gate_id UUID,
    p_days_back INT DEFAULT 30
) RETURNS TABLE (
    gate_id UUID,
    gate_code VARCHAR,
    gate_name VARCHAR,
    total_incidents BIGINT,
    tailgating_count BIGINT,
    unauthorized_count BIGINT,
    avg_risk_score FLOAT,
    critical_incidents BIGINT,
    latest_incident_time TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        g.id AS gate_id,
        g.gate_code,
        g.gate_name,
        COUNT(i.id) AS total_incidents,
        COUNT(CASE WHEN i.incident_type = 'TAILGATING' THEN 1 END) AS tailgating_count,
        COUNT(CASE WHEN i.incident_type = 'UNAUTHORIZED_ENTRY' THEN 1 END) AS unauthorized_count,
        COALESCE(ROUND(AVG(i.risk_score)::NUMERIC, 2)::FLOAT, 0.0) AS avg_risk_score,
        COUNT(CASE WHEN i.severity = 'CRITICAL' THEN 1 END) AS critical_incidents,
        MAX(i.created_at) AS latest_incident_time
    FROM gates g
    LEFT JOIN incidents i ON g.id = i.gate_id 
        AND i.created_at >= (CURRENT_TIMESTAMP - (p_days_back || ' days')::INTERVAL)
    WHERE g.id = p_gate_id
    GROUP BY g.id, g.gate_code, g.gate_name;
END;
$$ LANGUAGE plpgsql STABLE;


-- Function 3: Zone Hierarchy Traversal (Recursive CTE encapsulated in SQL function)
CREATE OR REPLACE FUNCTION get_zone_hierarchy(
    p_root_zone_id UUID
) RETURNS TABLE (
    zone_id UUID,
    zone_name VARCHAR,
    parent_zone_id UUID,
    depth INT,
    zone_path TEXT,
    sensitivity_level INT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE zone_tree AS (
        -- Anchor Member: Root zone
        SELECT 
            z.id AS zone_id,
            z.zone_name,
            z.parent_zone_id,
            1 AS depth,
            z.zone_name::TEXT AS zone_path,
            z.sensitivity_level
        FROM zones z
        WHERE z.id = p_root_zone_id
        
        UNION ALL
        
        -- Recursive Member: Child zones
        SELECT 
            c.id AS zone_id,
            c.zone_name,
            c.parent_zone_id,
            zt.depth + 1 AS depth,
            (zt.zone_path || ' -> ' || c.zone_name)::TEXT AS zone_path,
            c.sensitivity_level
        FROM zones c
        JOIN zone_tree zt ON c.parent_zone_id = zt.zone_id
    )
    SELECT * FROM zone_tree ORDER BY depth, zone_name;
END;
$$ LANGUAGE plpgsql STABLE;
