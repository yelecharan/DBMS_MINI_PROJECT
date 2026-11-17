"""Dashboard + "Query Lab": the SQL queries and MongoDB pipelines from the report,
executed live against the real databases and returned together with their source."""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth import CurrentUser, get_current_user
from ..db import mongo_db, pg_session, rows
from ..deps import not_found
from ..mongo_setup import ALERTS, OBSERVATIONS, REPORT

router = APIRouter(prefix="/api", tags=["Dashboard & Analytics"])

SQL_QUERIES: dict[str, dict] = {
    "join_scan_history": {
        "title": "INNER JOIN (4 tables) - scan history", "category": "JOIN",
        "sql": """SELECT a.scan_id, a.scan_time, e.name AS employee, e.department,
       c.card_no, g.gate_name, a.access_result
FROM access_logs a
JOIN cards     c ON c.card_id = a.card_id
JOIN employees e ON e.emp_id  = c.emp_id
JOIN gates     g ON g.gate_id = a.gate_id
ORDER BY a.scan_time DESC
LIMIT 15"""},
    "join_incident_details": {
        "title": "Multi-table JOIN (5 tables) - incident details", "category": "JOIN",
        "sql": """SELECT i.incident_id, i.severity, i.status, g.gate_name,
       e.name AS card_holder, c.card_no, a.scan_time, i.detected_time
FROM incidents i
JOIN access_logs a ON a.scan_id = i.scan_id
JOIN gates       g ON g.gate_id = a.gate_id
JOIN cards       c ON c.card_id = a.card_id
JOIN employees   e ON e.emp_id  = c.emp_id
ORDER BY i.detected_time DESC"""},
    "left_join_gate_usage": {
        "title": "LEFT JOIN - every gate with its scan count", "category": "JOIN",
        "sql": """SELECT g.gate_id, g.gate_name, g.status, COUNT(a.scan_id) AS scans
FROM gates g
LEFT JOIN access_logs a ON a.gate_id = g.gate_id
GROUP BY g.gate_id, g.gate_name, g.status
ORDER BY scans DESC"""},
    "left_join_unused_cards": {
        "title": "LEFT JOIN ... IS NULL - cards never used", "category": "JOIN",
        "sql": """SELECT c.card_no, e.name, c.status, c.issue_date
FROM cards c
JOIN employees e        ON e.emp_id  = c.emp_id
LEFT JOIN access_logs a ON a.card_id = c.card_id
WHERE a.scan_id IS NULL"""},
    "nested_in_incident_employees": {
        "title": "Nested IN subqueries - employees linked to incidents", "category": "NESTED",
        "sql": """SELECT emp_id, name, department
FROM employees
WHERE emp_id IN (SELECT c.emp_id FROM cards c
                 WHERE c.card_id IN (SELECT a.card_id FROM access_logs a
                                     WHERE a.scan_id IN (SELECT scan_id FROM incidents)))"""},
    "nested_busy_gates": {
        "title": "Nested scalar subquery + HAVING - gates busier than average",
        "category": "NESTED",
        "sql": """SELECT g.gate_name, COUNT(*) AS scans
FROM access_logs a JOIN gates g ON g.gate_id = a.gate_id
GROUP BY g.gate_name
HAVING COUNT(*) > (SELECT AVG(cnt) FROM (SELECT COUNT(*) AS cnt
                                         FROM access_logs GROUP BY gate_id) t)"""},
    "correlated_latest_scan": {
        "title": "Correlated subquery - each employee's latest scan", "category": "CORRELATED",
        "sql": """SELECT e.name, g.gate_name, a.scan_time
FROM access_logs a
JOIN cards c     ON c.card_id = a.card_id
JOIN employees e ON e.emp_id  = c.emp_id
JOIN gates g     ON g.gate_id = a.gate_id
WHERE a.scan_time = (SELECT MAX(a2.scan_time)
                     FROM access_logs a2 JOIN cards c2 ON c2.card_id = a2.card_id
                     WHERE c2.emp_id = e.emp_id)
ORDER BY a.scan_time DESC"""},
    "correlated_burst_scans": {
        "title": "Correlated EXISTS - scans with another scan at the same gate within 10 s",
        "category": "CORRELATED",
        "sql": """SELECT a.scan_id, a.gate_id, a.scan_time, a.access_result
FROM access_logs a
WHERE EXISTS (SELECT 1 FROM access_logs b
              WHERE b.gate_id = a.gate_id AND b.scan_id <> a.scan_id
                AND b.access_result = 'GRANTED'
                AND b.scan_time BETWEEN a.scan_time - INTERVAL '10 seconds'
                                    AND a.scan_time + INTERVAL '10 seconds')
ORDER BY a.scan_time"""},
    "correlated_above_dept_avg": {
        "title": "Correlated - employees scanning more than their department average",
        "category": "CORRELATED",
        "sql": """SELECT e.name, e.department,
       (SELECT COUNT(*) FROM access_logs a JOIN cards c ON c.card_id = a.card_id
        WHERE c.emp_id = e.emp_id) AS scans
FROM employees e
WHERE (SELECT COUNT(*) FROM access_logs a JOIN cards c ON c.card_id = a.card_id
       WHERE c.emp_id = e.emp_id)
    > (SELECT COUNT(a2.scan_id)::numeric / COUNT(DISTINCT e2.emp_id)
       FROM employees e2
       JOIN cards c2 ON c2.emp_id = e2.emp_id
       LEFT JOIN access_logs a2 ON a2.card_id = c2.card_id
       WHERE e2.department = e.department)
ORDER BY scans DESC"""},
    "agg_severity": {
        "title": "Aggregate + GROUP BY - incidents per severity", "category": "AGGREGATE",
        "sql": """SELECT severity, COUNT(*) AS total,
       COUNT(*) FILTER (WHERE status IN ('OPEN','INVESTIGATING')) AS still_open
FROM incidents
GROUP BY severity
ORDER BY total DESC"""},
    "having_risky_gates": {
        "title": "GROUP BY + HAVING - gates with 2 or more incidents", "category": "AGGREGATE",
        "sql": """SELECT g.gate_name, COUNT(i.incident_id) AS incidents
FROM gates g
JOIN access_logs a ON a.gate_id = g.gate_id
JOIN incidents   i ON i.scan_id = a.scan_id
GROUP BY g.gate_name
HAVING COUNT(i.incident_id) >= 2
ORDER BY incidents DESC"""},
    "agg_department": {
        "title": "Aggregates - department access summary", "category": "AGGREGATE",
        "sql": """SELECT e.department, COUNT(a.scan_id) AS scans,
       SUM(CASE WHEN a.access_result = 'DENIED' THEN 1 ELSE 0 END) AS denied,
       MIN(a.scan_time) AS first_scan, MAX(a.scan_time) AS last_scan
FROM employees e
JOIN cards c ON c.emp_id = e.emp_id
LEFT JOIN access_logs a ON a.card_id = c.card_id
GROUP BY e.department
ORDER BY scans DESC"""},
    "cte_open_by_employee": {
        "title": "CTE - open incidents per employee", "category": "CTE",
        "sql": """WITH open_incidents AS (
    SELECT i.*, a.card_id
    FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id
    WHERE i.status IN ('OPEN','INVESTIGATING')
),
per_employee AS (
    SELECT c.emp_id, COUNT(*) AS open_cnt
    FROM open_incidents o JOIN cards c ON c.card_id = o.card_id
    GROUP BY c.emp_id
)
SELECT e.name, e.department, p.open_cnt
FROM per_employee p JOIN employees e ON e.emp_id = p.emp_id
ORDER BY p.open_cnt DESC"""},
    "recursive_daily_trend": {
        "title": "RECURSIVE CTE - daily incidents for the last 14 days", "category": "RECURSIVE",
        "sql": """WITH RECURSIVE days(day) AS (
    SELECT CURRENT_DATE - 13
    UNION ALL
    SELECT day + 1 FROM days WHERE day < CURRENT_DATE
)
SELECT d.day, COUNT(i.incident_id) AS incidents
FROM days d
LEFT JOIN incidents i ON i.detected_time::date = d.day
GROUP BY d.day
ORDER BY d.day"""},
    "recursive_burst_chains": {
        "title": "RECURSIVE CTE - tailgating burst chains (scans <= 10 s apart)",
        "category": "RECURSIVE",
        "sql": """WITH RECURSIVE ordered AS (
    SELECT scan_id, gate_id, scan_time,
           LAG(scan_time) OVER (PARTITION BY gate_id ORDER BY scan_time) AS prev_time
    FROM access_logs
),
chain AS (
    SELECT scan_id AS chain_start, scan_id, gate_id, scan_time, 1 AS depth
    FROM ordered
    WHERE prev_time IS NULL OR scan_time - prev_time > INTERVAL '10 seconds'
    UNION ALL
    SELECT ch.chain_start, o.scan_id, o.gate_id, o.scan_time, ch.depth + 1
    FROM chain ch
    JOIN ordered o ON o.gate_id = ch.gate_id AND o.prev_time = ch.scan_time
                  AND o.scan_time - ch.scan_time <= INTERVAL '10 seconds'
)
SELECT chain_start, gate_id, COUNT(*) AS scans_in_chain,
       MIN(scan_time) AS started, MAX(scan_time) AS ended
FROM chain
GROUP BY chain_start, gate_id
HAVING COUNT(*) > 1"""},
    "fn_gate_risk": {
        "title": "Stored function (CTE inside) - fn_gate_risk_summary()", "category": "FUNCTION",
        "sql": "SELECT * FROM fn_gate_risk_summary()"},
    "fn_authorized": {
        "title": "Stored functions - fn_authorized_count / fn_compute_severity",
        "category": "FUNCTION",
        "sql": """SELECT a.scan_id, g.gate_name, a.scan_time,
       fn_authorized_count(a.scan_id)         AS authorised_within_10s,
       fn_compute_severity(4, fn_authorized_count(a.scan_id)) AS severity_if_4_people
FROM access_logs a JOIN gates g ON g.gate_id = a.gate_id
ORDER BY a.scan_time DESC
LIMIT 10"""},
    "triggers_catalog": {
        "title": "Catalog - triggers defined on GateSentry tables", "category": "FUNCTION",
        "sql": """SELECT event_object_table AS table_name, trigger_name,
       action_timing AS timing, string_agg(event_manipulation, ', ') AS events
FROM information_schema.triggers
WHERE trigger_schema = 'public'
GROUP BY event_object_table, trigger_name, action_timing
ORDER BY 1, 2"""},
    "rbac_privileges": {
        "title": "Catalog - database privileges of gs_admin / gs_security", "category": "RBAC",
        "sql": """SELECT grantee, table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
FROM information_schema.role_table_grants
WHERE grantee IN ('gs_admin','gs_security')
GROUP BY grantee, table_name
ORDER BY grantee, table_name"""},
}

MONGO_PIPELINES: dict[str, dict] = {
    "excess_per_gate": {
        "title": "Observations - unauthorised people per gate ($project, $group, $sort)",
        "collection": OBSERVATIONS,
        "pipeline": [
            {"$project": {"gate": "$location.gate_name",
                          "excess": {"$subtract": ["$observed_count", "$authorized_count"]}}},
            {"$group": {"_id": "$gate", "observations": {"$sum": 1},
                        "unauthorised": {"$sum": "$excess"}}},
            {"$sort": {"unauthorised": -1}},
        ]},
    "alerts_by_status": {
        "title": "Alerts - count by ack_status and alert_type ($group)",
        "collection": ALERTS,
        "pipeline": [
            {"$group": {"_id": {"ack_status": "$ack_status", "type": "$alert_type"},
                        "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]},
    "alerts_lookup_observations": {
        "title": "Alerts joined with Observations ($match, $lookup, $size)",
        "collection": ALERTS,
        "pipeline": [
            {"$match": {"ack_status": "PENDING"}},
            {"$lookup": {"from": OBSERVATIONS, "localField": "incident_id",
                         "foreignField": "incident_id", "as": "observations"}},
            {"$project": {"_id": 0, "alert_id": 1, "incident_id": 1, "severity": 1,
                          "observation_count": {"$size": "$observations"},
                          "observed": "$observations.observed_count"}},
        ]},
    "attachments_unwind": {
        "title": "Report - attachments per file type ($unwind array)",
        "collection": REPORT,
        "pipeline": [
            {"$unwind": "$attachments"},
            {"$group": {"_id": "$attachments.file_type", "files": {"$push": "$attachments.file_name"},
                        "count": {"$sum": 1}}},
        ]},
    "daily_observations": {
        "title": "Observations per day ($dateToString, $group, $sort)",
        "collection": OBSERVATIONS,
        "pipeline": [
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp",
                                                  "timezone": "Asia/Kolkata"}},
                        "observations": {"$sum": 1},
                        "people_observed": {"$sum": "$observed_count"}}},
            {"$sort": {"_id": 1}},
        ]},
}


@router.get("/dashboard")
def dashboard(user: CurrentUser = Depends(get_current_user)):
    with pg_session(user.role) as conn:
        counts = rows(conn.execute(text("""
            SELECT (SELECT COUNT(*) FROM employees)   AS employees,
                   (SELECT COUNT(*) FROM cards)       AS cards,
                   (SELECT COUNT(*) FROM cards WHERE status = 'ACTIVE') AS active_cards,
                   (SELECT COUNT(*) FROM gates)       AS gates,
                   (SELECT COUNT(*) FROM access_logs) AS scans,
                   (SELECT COUNT(*) FROM access_logs WHERE access_result = 'DENIED') AS denied_scans,
                   (SELECT COUNT(*) FROM incidents)   AS incidents,
                   (SELECT COUNT(*) FROM incidents WHERE status IN ('OPEN','INVESTIGATING'))
                                                      AS open_incidents""")))[0]
        trend = rows(conn.execute(text(SQL_QUERIES["recursive_daily_trend"]["sql"])))
        gate_risk = rows(conn.execute(text("SELECT * FROM fn_gate_risk_summary()")))
        recent = rows(conn.execute(text("""
            SELECT i.incident_id, i.detected_time, i.severity, i.status, g.gate_name,
                   e.name AS employee
            FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id
            JOIN gates g ON g.gate_id = a.gate_id
            JOIN cards c ON c.card_id = a.card_id JOIN employees e ON e.emp_id = c.emp_id
            ORDER BY i.detected_time DESC LIMIT 5""")))
    counts["pending_alerts"] = mongo_db[ALERTS].count_documents({"ack_status": "PENDING"})
    counts["observations"] = mongo_db[OBSERVATIONS].estimated_document_count()
    counts["reports"] = mongo_db[REPORT].estimated_document_count()
    return {"counts": counts, "trend": trend, "gate_risk": gate_risk, "recent_incidents": recent}


@router.get("/analytics/sql")
def list_sql_queries(user: CurrentUser = Depends(get_current_user)):
    return [{"key": k, "title": v["title"], "category": v["category"], "sql": v["sql"]}
            for k, v in SQL_QUERIES.items()]


@router.get("/analytics/sql/{key}")
def run_sql_query(key: str, user: CurrentUser = Depends(get_current_user)):
    q = SQL_QUERIES.get(key)
    if not q:
        raise not_found("Query", key)
    with pg_session(user.role) as conn:
        result = conn.execute(text(q["sql"]))
        return {"key": key, "title": q["title"], "sql": q["sql"],
                "columns": list(result.keys()), "rows": rows(result)}


@router.get("/analytics/mongo")
def list_pipelines(user: CurrentUser = Depends(get_current_user)):
    return [{"key": k, "title": v["title"], "collection": v["collection"],
             "pipeline": v["pipeline"]} for k, v in MONGO_PIPELINES.items()]


@router.get("/analytics/mongo/{key}")
def run_pipeline(key: str, user: CurrentUser = Depends(get_current_user)):
    p = MONGO_PIPELINES.get(key)
    if not p:
        raise not_found("Pipeline", key)
    docs = list(mongo_db[p["collection"]].aggregate(p["pipeline"]))
    return {"key": key, "title": p["title"], "collection": p["collection"],
            "pipeline": p["pipeline"], "rows": docs}
