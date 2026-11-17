-- ============================================================================
-- GATESENTRY ADVANCED SQL QUERIES REFERENCE
-- Project: GateSentry - Explainable Office Tailgating Detection System
-- Target DBMS: PostgreSQL 14+
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. MULTI-TABLE JOINS (INNER, LEFT, RIGHT)
-- ----------------------------------------------------------------------------

-- Query 1.1: Comprehensive Incident Audit Dossier (5-table INNER/LEFT JOIN)
-- Retrieves every incident with gate, zone, site, assigned security officer,
-- and total logged investigation actions.
SELECT 
    i.id AS incident_id,
    i.incident_type,
    i.severity,
    i.risk_score,
    i.status,
    i.authorized_count,
    i.observed_count,
    i.unmatched_count,
    g.gate_code,
    g.gate_name,
    z.zone_name,
    z.sensitivity_level,
    s.site_name,
    COALESCE(u.full_name, 'UNASSIGNED') AS investigator_name,
    COUNT(ia.id) AS total_investigation_notes
FROM incidents i
INNER JOIN gates g ON i.gate_id = g.id
INNER JOIN zones z ON g.zone_id = z.id
INNER JOIN sites s ON z.site_id = s.id
LEFT JOIN users u ON i.assigned_to = u.id
LEFT JOIN incident_actions ia ON i.id = ia.incident_id
GROUP BY 
    i.id, i.incident_type, i.severity, i.risk_score, i.status,
    i.authorized_count, i.observed_count, i.unmatched_count,
    g.gate_code, g.gate_name, z.zone_name, z.sensitivity_level, s.site_name, u.full_name
ORDER BY i.risk_score DESC;

-- Query 1.2: RIGHT JOIN Demonstration (Audit of All Configured Gates vs Active Sessions)
-- Ensures all gates are shown even if they have had zero gate sessions logged.
SELECT 
    g.gate_code,
    g.gate_name,
    gs.id AS session_id,
    gs.status AS session_status,
    gs.opened_at,
    gs.unmatched_crossings
FROM gate_sessions gs
RIGHT JOIN gates g ON gs.gate_id = g.id
ORDER BY g.gate_code;


-- ----------------------------------------------------------------------------
-- 2. NESTED QUERIES (SUBQUERIES)
-- ----------------------------------------------------------------------------

-- Query 2.1: Find Incidents Whose Risk Scores Exceed the Overall Average Risk Score
SELECT 
    i.id,
    i.incident_type,
    i.severity,
    i.risk_score,
    i.summary,
    g.gate_name
FROM incidents i
JOIN gates g ON i.gate_id = g.id
WHERE i.risk_score > (
    SELECT AVG(risk_score) 
    FROM incidents
)
ORDER BY i.risk_score DESC;

-- Query 2.2: Identify Employees Who Have Badged In at Gates with Unmatched Crossings
SELECT 
    e.employee_code,
    e.full_name,
    e.department,
    ae.event_timestamp,
    g.gate_name
FROM employees e
JOIN access_credentials ac ON e.id = ac.employee_id
JOIN access_events ae ON ac.id = ae.credential_id
JOIN gates g ON ae.gate_id = g.id
WHERE ae.gate_id IN (
    SELECT DISTINCT gate_id 
    FROM incidents 
    WHERE severity IN ('HIGH', 'CRITICAL')
)
ORDER BY ae.event_timestamp DESC;


-- ----------------------------------------------------------------------------
-- 3. CORRELATED QUERIES
-- ----------------------------------------------------------------------------

-- Query 3.1: Find Gates Where the Incident Count Exceeds the Average Incident Count
-- of Gates in the Same Site (Correlated Subquery)
SELECT 
    g.id AS gate_id,
    g.gate_name,
    s.site_name,
    (
        SELECT COUNT(*) 
        FROM incidents i 
        WHERE i.gate_id = g.id
    ) AS gate_incident_count
FROM gates g
JOIN zones z ON g.zone_id = z.id
JOIN sites s ON z.site_id = s.id
WHERE (
    SELECT COUNT(*) 
    FROM incidents i 
    WHERE i.gate_id = g.id
) > (
    -- Average incident count per gate within this specific site
    SELECT AVG(site_gate_incidents.cnt)
    FROM (
        SELECT COUNT(i2.id) AS cnt
        FROM gates g2
        JOIN zones z2 ON g2.zone_id = z2.id
        LEFT JOIN incidents i2 ON g2.id = i2.gate_id
        WHERE z2.site_id = s.id
        GROUP BY g2.id
    ) AS site_gate_incidents
);


-- ----------------------------------------------------------------------------
-- 4. RECURSIVE COMMON TABLE EXPRESSIONS (CTE)
-- ----------------------------------------------------------------------------

-- Query 4.1: Hierarchical Recursive Traversal of Building Zones
-- Traverses parent-child relationships from campus down to secure server rooms.
WITH RECURSIVE ZoneTree AS (
    -- Anchor Member: Root zones without parents
    SELECT 
        id,
        site_id,
        parent_zone_id,
        zone_name,
        zone_type,
        sensitivity_level,
        1 AS level,
        zone_name::TEXT AS path
    FROM zones
    WHERE parent_zone_id IS NULL

    UNION ALL

    -- Recursive Member: Child zones joined to their parents
    SELECT 
        c.id,
        c.site_id,
        c.parent_zone_id,
        c.zone_name,
        c.zone_type,
        c.sensitivity_level,
        zt.level + 1 AS level,
        (zt.path || ' / ' || c.zone_name)::TEXT AS path
    FROM zones c
    INNER JOIN ZoneTree zt ON c.parent_zone_id = zt.id
)
SELECT 
    level,
    path,
    zone_type,
    sensitivity_level
FROM ZoneTree
ORDER BY path;


-- ----------------------------------------------------------------------------
-- 5. ADVANCED CTE & WINDOW FUNCTIONS
-- ----------------------------------------------------------------------------

-- Query 5.1: Incident Ranking and Risk Quartile Analysis across Gates
WITH GateMetrics AS (
    SELECT 
        g.id AS gate_id,
        g.gate_name,
        z.zone_name,
        COUNT(i.id) AS total_incidents,
        ROUND(AVG(i.risk_score)::NUMERIC, 2) AS avg_risk,
        MAX(i.risk_score) AS max_risk,
        SUM(i.unmatched_count) AS total_unmatched_people
    FROM gates g
    JOIN zones z ON g.zone_id = z.id
    LEFT JOIN incidents i ON g.id = i.gate_id
    GROUP BY g.id, g.gate_name, z.zone_name
),
RankedGates AS (
    SELECT 
        gm.*,
        DENSE_RANK() OVER (ORDER BY gm.total_incidents DESC, gm.avg_risk DESC) AS incident_rank,
        NTILE(4) OVER (ORDER BY gm.avg_risk DESC) AS risk_quartile
    FROM GateMetrics gm
)
SELECT 
    incident_rank,
    gate_name,
    zone_name,
    total_incidents,
    avg_risk,
    total_unmatched_people,
    CASE risk_quartile
        WHEN 1 THEN 'Tier 1 - Highest Threat Level'
        WHEN 2 THEN 'Tier 2 - Elevated Threat Level'
        WHEN 3 THEN 'Tier 3 - Moderate Threat Level'
        ELSE 'Tier 4 - Normal Operations'
    END AS threat_classification
FROM RankedGates
ORDER BY incident_rank;
