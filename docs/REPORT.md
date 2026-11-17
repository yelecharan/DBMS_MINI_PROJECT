# DBMS Mini Project Report

## 1. Title

**GateSentry – A Tailgating Detection and Management System using PostgreSQL and MongoDB**

## 2. Students

| SRN | Name |
|---|---|
| PES1UG24CS535 | Vilohith Sree Sai Reddy Daggolu |
| PES1UG25CS856 | Yele Charan |

GitHub: https://github.com/yelecharan/DBMS_MINI_PROJECT

## 3. Abstract

Tailgating, also called piggy-backing, happens when an unauthorised person follows an authorised employee through a secured gate on a single card scan. GateSentry is a database-driven system for recording and investigating these events. Structured, strongly related data (employees, their access cards, gates, card-scan logs and incidents) is stored in **PostgreSQL**, which enforces it with primary/foreign keys, CHECK and UNIQUE constraints, triggers, stored functions and procedures. Semi-structured, growing investigation data (guard observations, incident reports with attachment lists, and alerts with acknowledgement details) is stored in **MongoDB** collections that reference the SQL incident through `incident_id`.

A guard compares the number of people seen at a gate with the number of authorised scans. The stored function `fn_authorized_count` counts the GRANTED scans at that gate within ±10 seconds. If more people passed through, `fn_report_tailgating` creates an incident with a severity computed from the excess, and the backend stores an observation and an alert in MongoDB. A FastAPI backend serves a Next.js dashboard. Authentication uses PostgreSQL login roles, and role-based access control with three roles (Administrator, Security Staff and a read-only Viewer) is enforced both by the API and by PostgreSQL GRANTs through `SET LOCAL ROLE`. No machine learning or CCTV is used. Observations are entered by hand or simulated.

## 4. Tech Stack

| Layer | Technology | Why it was chosen (technology justification) |
|---|---|---|
| Relational DB | **PostgreSQL 18** | ACID transactions, rich constraints (CHECK, deferrable constraint triggers), PL/pgSQL functions, procedures and triggers, recursive CTEs, window functions, and a fine-grained role and privilege system (including column-level GRANT) that we use for RBAC. Employees→Cards→Access_Logs→Incidents is highly relational and needs referential integrity. |
| Document DB | **MongoDB 9 Community** | Observations, reports and alerts are semi-structured and change shape (nested `location` / `reported_by` / `acknowledged` documents, `tags` / `attachments` / `recipients` arrays) and are written often. `$jsonSchema` validation still keeps them consistent, and the aggregation pipeline (`$group`, `$lookup`, `$unwind`, `$facet`) suits the analytics. |
| Backend | **Python FastAPI** + SQLAlchemy 2 (psycopg 3) + PyMongo | Automatic request validation (Pydantic) and OpenAPI docs. Raw SQL through SQLAlchemy `text()` keeps the SQL visible for a DBMS course. |
| Auth | PostgreSQL SCRAM-SHA-256 roles + JWT (PyJWT) | Passwords are hashed by the DBMS itself, and the same roles enforce privileges inside the database. |
| Frontend | **Next.js 15**, TypeScript, Tailwind CSS 4 | Type-safe React with file-based routing. Tailwind gives a clean dashboard without a heavy UI library. |
| Tools | pgAdmin 4, MongoDB Compass, pytest | GUIs for checking the data; automated tests against the real servers. |

## 5. SQL – Database Commands

The full scripts are in `database/postgres/`. The key commands are below. `06_dml_demo.sql` is a single demo file that lists and counts the tables, shows their structure and data, and runs INSERT, UPDATE and DELETE on every table.

### 5.1 Relational schema (from the ER diagram)

| Relation | Attributes (PK **bold**, FK *italic*) | Constraints |
|---|---|---|
| R1 employees | **emp_id**, name, department, phone | phone UNIQUE + CHECK `^\+?[0-9]{10,13}$`, NOT NULLs |
| R2 cards | **card_id**, *emp_id*→employees, card_no, issue_date, expiry_date, status | card_no UNIQUE, status IN (ACTIVE, INACTIVE, EXPIRED, LOST), CHECK expiry > issue, FK ON DELETE CASCADE |
| R3 gates | **gate_id**, gate_name, location, type, status | gate_name UNIQUE, type IN (ENTRY, EXIT, BIDIRECTIONAL), status IN (ACTIVE, INACTIVE, MAINTENANCE) |
| R4 access_logs | **scan_id**, *card_id*→cards, *gate_id*→gates, scan_time, access_result | access_result IN (GRANTED, DENIED), FKs ON DELETE RESTRICT (audit trail) |
| R5 incidents | **incident_id**, *scan_id*→access_logs, detected_time, severity, status | severity IN (LOW…CRITICAL), status IN (OPEN, INVESTIGATING, RESOLVED, FALSE_ALARM), FK RESTRICT |

How the cardinality and participation rules are implemented:
* Employees (1)–(N) Cards, **total on both sides**. `cards.emp_id NOT NULL` makes every card belong to an employee. The deferred constraint trigger `trg_employee_requires_card` makes every employee own at least one card, checked at COMMIT. The procedure `sp_add_employee_with_card` inserts both in one transaction.
* Cards / Gates (1)–(N) Access_Logs and Access_Logs (1)–(N) Incidents. The many side is total and enforced with `NOT NULL` foreign keys. Total participation on the *one* side (every card or gate has at least one scan) is not enforced, because a newly issued card or newly installed gate cannot have a scan yet.

### 5.2 DDL (excerpt of `01_schema.sql`)
```sql
DROP TABLE IF EXISTS incidents, access_logs, gates, cards, employees CASCADE;

CREATE TABLE employees (
    emp_id      SERIAL       PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    department  VARCHAR(50)  NOT NULL,
    phone       VARCHAR(15)  NOT NULL,
    CONSTRAINT uq_employees_phone  UNIQUE (phone),
    CONSTRAINT chk_employees_phone CHECK (phone ~ '^\+?[0-9]{10,13}$')
);

CREATE TABLE cards (
    card_id      SERIAL      PRIMARY KEY,
    emp_id       INT         NOT NULL,
    card_no      VARCHAR(20) NOT NULL,
    issue_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
    expiry_date  DATE        NOT NULL,
    status       VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_cards_employee FOREIGN KEY (emp_id)
        REFERENCES employees(emp_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uq_cards_card_no UNIQUE (card_no),
    CONSTRAINT chk_cards_status CHECK (status IN ('ACTIVE','INACTIVE','EXPIRED','LOST')),
    CONSTRAINT chk_cards_dates  CHECK (expiry_date > issue_date)
);

CREATE TABLE access_logs (
    scan_id        SERIAL      PRIMARY KEY,
    card_id        INT         NOT NULL REFERENCES cards(card_id) ON DELETE RESTRICT,
    gate_id        INT         NOT NULL REFERENCES gates(gate_id) ON DELETE RESTRICT,
    scan_time      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    access_result  VARCHAR(10) NOT NULL DEFAULT 'GRANTED'
);

ALTER TABLE access_logs
    ADD CONSTRAINT chk_logs_result CHECK (access_result IN ('GRANTED','DENIED'));
ALTER TABLE incidents
    ADD CONSTRAINT chk_incidents_severity CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    ADD CONSTRAINT chk_incidents_status   CHECK (status IN ('OPEN','INVESTIGATING','RESOLVED','FALSE_ALARM'));

CREATE INDEX idx_logs_gate_time   ON access_logs(gate_id, scan_time);
CREATE INDEX idx_incidents_status ON incidents(status);
```

### 5.3 DML
```sql
CALL sp_add_employee_with_card('Nikhil Bhat','Engineering','9123456780','GS-2001', CURRENT_DATE + 365);
INSERT INTO access_logs (card_id, gate_id) VALUES (1, 1) RETURNING *;
SELECT card_no, status, expiry_date FROM cards
 WHERE status = 'ACTIVE' AND expiry_date < CURRENT_DATE + 90 ORDER BY expiry_date;
UPDATE gates     SET status = 'MAINTENANCE'   WHERE gate_name = 'Parking Exit';
UPDATE incidents SET status = 'INVESTIGATING' WHERE status = 'OPEN' AND severity = 'CRITICAL';
DELETE FROM cards c WHERE c.status = 'LOST'
   AND NOT EXISTS (SELECT 1 FROM access_logs a WHERE a.card_id = c.card_id);
```
The same INSERT / SELECT / UPDATE / DELETE statements run behind every form in the web app (`backend/app/routers/*.py`).

### 5.4 Join, nested, correlated and recursive queries
```sql
-- Multi-table JOIN (5 tables): incident details
SELECT i.incident_id, i.severity, i.status, g.gate_name, e.name AS card_holder, c.card_no
FROM incidents i
JOIN access_logs a ON a.scan_id = i.scan_id
JOIN gates       g ON g.gate_id = a.gate_id
JOIN cards       c ON c.card_id = a.card_id
JOIN employees   e ON e.emp_id  = c.emp_id;

-- LEFT JOIN: every gate with its scan count (unused gates show 0)
SELECT g.gate_name, COUNT(a.scan_id) AS scans
FROM gates g LEFT JOIN access_logs a ON a.gate_id = g.gate_id
GROUP BY g.gate_name;

-- Nested: employees whose scans led to an incident
SELECT name FROM employees WHERE emp_id IN
  (SELECT emp_id FROM cards WHERE card_id IN
    (SELECT card_id FROM access_logs WHERE scan_id IN (SELECT scan_id FROM incidents)));

-- Correlated EXISTS: scans with another GRANTED scan at the same gate within 10 s
SELECT a.scan_id, a.gate_id, a.scan_time FROM access_logs a
WHERE EXISTS (SELECT 1 FROM access_logs b
              WHERE b.gate_id = a.gate_id AND b.scan_id <> a.scan_id
                AND b.access_result = 'GRANTED'
                AND b.scan_time BETWEEN a.scan_time - INTERVAL '10 seconds'
                                    AND a.scan_time + INTERVAL '10 seconds');

-- GROUP BY + HAVING: high-risk gates
SELECT g.gate_name, COUNT(i.incident_id) AS incidents
FROM gates g JOIN access_logs a ON a.gate_id = g.gate_id
JOIN incidents i ON i.scan_id = a.scan_id
GROUP BY g.gate_name HAVING COUNT(i.incident_id) >= 2;

-- RECURSIVE CTE: 14-day calendar so days without incidents still appear
WITH RECURSIVE days(day) AS (
    SELECT CURRENT_DATE - 13
    UNION ALL SELECT day + 1 FROM days WHERE day < CURRENT_DATE)
SELECT d.day, COUNT(i.incident_id) AS incidents
FROM days d LEFT JOIN incidents i ON i.detected_time::date = d.day
GROUP BY d.day ORDER BY d.day;
```
`05_queries.sql` (and the **Query Lab** page, which has 20) contain the queries, including a correlated "above department average" query, a CTE ranking open incidents per employee, and a recursive CTE that chains consecutive scans ≤ 10 s apart into tailgating bursts.

### 5.5 Advanced SQL – functions, procedures, triggers, CTE

| Object | Type | Purpose |
|---|---|---|
| `fn_authorized_count(scan_id, window)` | function | GRANTED scans at the same gate within ±window seconds |
| `fn_compute_severity(observed, authorized)` | function | excess 1→LOW, 2→MEDIUM, 3–4→HIGH, ≥5→CRITICAL |
| `fn_report_tailgating(scan_id, observed, authorized)` | function | validates the counts and inserts the incident, returns its id |
| `fn_gate_risk_summary()` | function (2 CTEs) | scans, denied scans, incidents and risk % per gate |
| `sp_add_employee_with_card(...)` | procedure | employee and first card in one transaction |
| `sp_deactivate_employee_cards(emp_id)` | procedure | blocks all cards of an employee |
| `trg_employee_requires_card`, `trg_card_removal_keeps_one` | deferred constraint triggers | total participation Employees–Cards |
| `trg_card_auto_expire` | BEFORE INSERT/UPDATE | marks expired cards `EXPIRED` |
| `trg_validate_access_log` | BEFORE INSERT | forces `DENIED` for inactive/lost/expired cards or gates that are not active |
| `trg_validate_incident_time` | BEFORE INSERT/UPDATE | detected_time cannot be earlier than scan_time (cross-table rule) |

```sql
CREATE OR REPLACE FUNCTION fn_report_tailgating(p_scan_id INT, p_observed INT, p_authorized INT DEFAULT NULL)
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE v_auth INT; v_incident INT;
BEGIN
    v_auth := COALESCE(p_authorized, fn_authorized_count(p_scan_id));
    IF p_observed <= v_auth THEN
        RAISE EXCEPTION 'No tailgating: % people observed, % authorised scans', p_observed, v_auth
              USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO incidents(scan_id, detected_time, severity, status)
    VALUES (p_scan_id, LOCALTIMESTAMP, fn_compute_severity(p_observed, v_auth), 'OPEN')
    RETURNING incident_id INTO v_incident;
    RETURN v_incident;
END; $$;

CREATE OR REPLACE FUNCTION fn_validate_access_log() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_card_status VARCHAR; v_expiry DATE; v_gate_status VARCHAR;
BEGIN
    SELECT status, expiry_date INTO v_card_status, v_expiry FROM cards WHERE card_id = NEW.card_id;
    SELECT status INTO v_gate_status FROM gates WHERE gate_id = NEW.gate_id;
    IF v_card_status <> 'ACTIVE' OR v_expiry < NEW.scan_time::date OR v_gate_status <> 'ACTIVE' THEN
        NEW.access_result := 'DENIED';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER trg_validate_access_log BEFORE INSERT ON access_logs
    FOR EACH ROW EXECUTE FUNCTION fn_validate_access_log();

CREATE CONSTRAINT TRIGGER trg_employee_requires_card
    AFTER INSERT ON employees DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_check_employee_has_card();
```

**Demonstration file:** `07_advanced_sql_demo.sql` runs every routine above against the real data inside one transaction that ends in `ROLLBACK`:

| Section | What it shows |
|---|---|
| A | catalog listing of all routines and triggers |
| B.1 – B.4 | each of the 4 functions called, including `fn_report_tailgating` inserting an incident and refusing a case with no extra people |
| C.1 – C.2 | both procedures called, with the resulting rows |
| D.1 – D.5 | each of the 5 triggers firing: card auto-expired, scans forced to DENIED, incident before scan rejected, employee without card rejected, last card delete rejected |
| E.1 – E.3 | one CTE with two named sub-queries, plus two recursive CTEs (anchor member, recursive member, stop condition) |
| F | bonus: a VIEW, window functions (`RANK`, `SUM … OVER`, `LAG`) and `SAVEPOINT` / `ROLLBACK TO SAVEPOINT` |

### 5.6 Role-based access control in the database (`03_roles.sql`)
```sql
CREATE ROLE gs_admin NOLOGIN;
CREATE ROLE gs_security NOLOGIN;
GRANT SELECT, INSERT, UPDATE, DELETE ON employees, cards, gates, access_logs, incidents TO gs_admin;
GRANT SELECT ON employees, cards, gates, access_logs, incidents TO gs_security;
GRANT INSERT ON access_logs, incidents TO gs_security;
GRANT UPDATE (status) ON incidents TO gs_security;          -- column-level privilege
CREATE ROLE gs_viewer NOLOGIN;                              -- limited, read-only user
GRANT SELECT ON cards, gates, access_logs, incidents TO gs_viewer;
GRANT SELECT (emp_id, name, department) ON employees TO gs_viewer;   -- phone hidden
-- created by init_db.py with passwords from .env (stored as SCRAM-SHA-256 hashes):
CREATE ROLE admin LOGIN PASSWORD '***' IN ROLE gs_admin;
CREATE ROLE guard LOGIN PASSWORD '***' IN ROLE gs_security;
CREATE ROLE viewer LOGIN PASSWORD '***' IN ROLE gs_viewer;
CREATE ROLE gatesentry_app LOGIN NOINHERIT PASSWORD '***';
GRANT gs_admin, gs_security, gs_viewer TO gatesentry_app WITH INHERIT FALSE, SET TRUE;
-- per request, inside the transaction:
SET LOCAL ROLE gs_security;
DELETE FROM incidents WHERE incident_id = 1;   -- ERROR: permission denied for table incidents
SET LOCAL ROLE gs_viewer;
SELECT phone FROM employees;                   -- ERROR: permission denied for table employees
```

| Action | Admin | Security staff | Viewer |
|---|:-:|:-:|:-:|
| View dashboard, gates, cards, scans, incidents, MongoDB data | ✅ | ✅ | ✅ |
| See employee phone numbers | ✅ | ✅ | ❌ (column-level GRANT) |
| Record scans, report tailgating, add observations/reports, acknowledge alerts | ✅ | ✅ | ❌ |
| Change incident status | ✅ | ✅ (`UPDATE(status)` only) | ❌ |
| Create/edit/delete employees, cards, gates; delete any record; manage alerts | ✅ | ❌ | ❌ |

## 6. NoSQL (MongoDB) – Database Commands

The full script is in `database/mongodb/mongo_commands.js`. `mongo_dml_demo.js` is a single demo file that lists and counts the collections, shows their validators, indexes and data, and runs insert, update and delete on every collection. Both can be run in Compass's MONGOSH tab. The backend runs the same operations through PyMongo (`backend/app/mongo_setup.py`, `routers/observations.py`, `reports.py`, `alerts.py`).

| Collection | Fields (from relational schema R6–R8) | Extra document features |
|---|---|---|
| Observations | obs_id, incident_id, method, observed_count, authorized_count, timestamp | nested `location {gate_id, gate_name, scan_id}`, `tags` array, `observed_by`, `notes` |
| Report | report_id, incident_id, description, reported_by, attachments, timestamp | `reported_by {username, role}` nested, `attachments [{file_name, file_type, note}]` array, text index |
| Alerts | alert_id, incident_id, alert_time, alert_type, ack_status, message | `acknowledged {by, at, comment}` nested, `recipients` array, `severity` |

```javascript
use("gatesentry");
db.createCollection("Observations", { validator: { $jsonSchema: {
  bsonType: "object",
  required: ["obs_id","incident_id","method","observed_count","authorized_count","timestamp"],
  properties: {
    incident_id: { bsonType: "int", minimum: 1 },
    method: { enum: ["MANUAL_HEADCOUNT","GUARD_PATROL","TURNSTILE_COUNTER","SIMULATED"] },
    observed_count: { bsonType: "int", minimum: 0 },
    location: { bsonType: "object" },
    tags: { bsonType: "array", items: { bsonType: "string" } } } } } });
db.Observations.createIndex({ obs_id: 1 }, { unique: true });
db.Observations.createIndex({ "location.gate_id": 1 });
db.Report.createIndex({ description: "text" });
db.Alerts.createIndex({ ack_status: 1, alert_time: -1 });

// CREATE
db.Observations.insertOne({ obs_id: "OBS-DEMO0001", incident_id: NumberInt(7), method: "MANUAL_HEADCOUNT",
  observed_count: NumberInt(6), authorized_count: NumberInt(1), timestamp: new Date(),
  location: { gate_id: NumberInt(3), gate_name: "Server Room", scan_id: NumberInt(22) },
  tags: ["tailgating", "critical"] });

// READ – filter on nested field, array element, field comparison, text search, sort
db.Observations.find({ "location.gate_name": "Server Room" }).sort({ timestamp: -1 });
db.Observations.find({ tags: "critical" });
db.Observations.find({ $expr: { $gte: [ { $subtract: ["$observed_count","$authorized_count"] }, 3 ] } });
db.Report.find({ $text: { $search: "server room" } });
db.Alerts.find({ ack_status: "PENDING", severity: { $in: ["HIGH","CRITICAL"] } }).sort({ alert_time: -1 });

// UPDATE – acknowledge, push/pull array elements
db.Alerts.updateOne({ alert_id: "ALT-DEMO0001", ack_status: "PENDING" },
  { $set: { ack_status: "ACKNOWLEDGED", acknowledged: { by: "guard", at: new Date(), comment: "Area secured" } } });
db.Report.updateOne({ report_id: "RPT-DEMO0001" },
  { $push: { attachments: { file_name: "visitor_badges.jpg", file_type: "image/jpeg" } } });
db.Report.updateOne({ report_id: "RPT-DEMO0001" }, { $pull: { attachments: { file_name: "visitor_badges.jpg" } } });

// DELETE
db.Alerts.deleteOne({ alert_id: "ALT-DEMO0002" });
db.Observations.deleteMany({ incident_id: 7 });     // used for cascade when an SQL incident is deleted

// AGGREGATION
db.Observations.aggregate([
  { $project: { gate: "$location.gate_name", excess: { $subtract: ["$observed_count","$authorized_count"] } } },
  { $group: { _id: "$gate", observations: { $sum: 1 }, unauthorised: { $sum: "$excess" } } },
  { $sort: { unauthorised: -1 } } ]);
db.Alerts.aggregate([
  { $match: { ack_status: "PENDING" } },
  { $lookup: { from: "Observations", localField: "incident_id", foreignField: "incident_id", as: "obs" } },
  { $project: { _id: 0, alert_id: 1, incident_id: 1, observation_count: { $size: "$obs" } } } ]);
db.Report.aggregate([ { $unwind: "$attachments" },
  { $group: { _id: "$attachments.file_type", count: { $sum: 1 } } } ]);
```

**Integration with SQL.** `incident_id` is an application-level reference. The backend (`deps.ensure_incident_exists`) refuses documents whose incident does not exist in PostgreSQL. Deleting an incident also deletes its MongoDB documents. Reporting tailgating creates the SQL incident first and then writes the Observation and Alert documents inside the still-open SQL transaction, so the incident is rolled back if MongoDB fails.

## 7. Next.js – Project Tree Structure

```
frontend/
├── next.config.ts
├── package.json
├── tsconfig.json
├── .env.example                    NEXT_PUBLIC_API_URL=http://localhost:8000
└── src/
    ├── app/
    │   ├── layout.tsx              root layout, AuthProvider
    │   ├── page.tsx                redirect → /dashboard
    │   ├── globals.css             Tailwind + small component classes
    │   ├── login/page.tsx          1. Login
    │   └── (app)/                  route group protected by login
    │       ├── layout.tsx          sidebar, user/role badge, logout, auth guard
    │       ├── dashboard/page.tsx  2. Dashboard
    │       ├── employees/page.tsx  3. Employees   (PostgreSQL)
    │       ├── cards/page.tsx      4. Cards
    │       ├── gates/page.tsx      5. Gates
    │       ├── access-logs/page.tsx 6. Access Logs (+ record scan, report tailgating)
    │       ├── incidents/page.tsx  7. Incidents
    │       ├── incidents/[id]/page.tsx  incident + linked MongoDB documents
    │       ├── observations/page.tsx 8. Observations (MongoDB)
    │       ├── reports/page.tsx    9. Reports
    │       ├── alerts/page.tsx     10. Alerts
    │       └── query-lab/page.tsx  runs the report's SQL queries / Mongo pipelines live
    ├── components/
    │   ├── ui.tsx                  DataTable (sorting), Modal, ConfirmDialog, Badge, Field, Select…
    │   └── TailgatingForm.tsx
    └── lib/
        ├── api.ts                  fetch wrapper (JWT header, error handling)
        ├── auth.tsx                AuthContext: login / logout / role
        ├── hooks.ts                useApi data-loading hook
        └── types.ts
```

## 8. Screenshots

The screenshots in `docs/screenshots/` were captured from the running application with live database data (`node docs/capture_screenshots.mjs`).

| | |
|---|---|
| Login ![](screenshots/login.png) | Dashboard ![](screenshots/dashboard.png) |
| Employees (admin) ![](screenshots/employees.png) | Employees (security staff: read-only) ![](screenshots/security_employees.png) |
| Cards ![](screenshots/cards.png) | Gates ![](screenshots/gates.png) |
| Access Logs ![](screenshots/access_logs.png) | Incidents ![](screenshots/incidents.png) |
| Incident detail (SQL + MongoDB) ![](screenshots/incident_detail.png) | Observations + aggregation ![](screenshots/observations.png) |
| Reports ![](screenshots/reports.png) | Alerts ![](screenshots/alerts.png) |
| Query Lab (recursive CTE) ![](screenshots/query_lab.png) | Incidents (security staff) ![](screenshots/security_incidents.png) |
| Employees (viewer: phone hidden) ![](screenshots/viewer_employees.png) | Incident detail (viewer: read-only) ![](screenshots/viewer_incident_detail.png) |

*Add your own pgAdmin 4 (tables, triggers, roles) and MongoDB Compass (collections, validation, indexes) screenshots and VS Code code screenshots here before you submit.*

Test run (`pytest`, against the real PostgreSQL 18 and MongoDB servers):
```
115 passed in 3.1s
  test_1_connectivity.py            8   PostgreSQL/MongoDB connection, tables, FKs, collections, validators, indexes
  test_2_sql_constraints.py        10   UNIQUE, CHECK, FK, NOT NULL, RESTRICT, total participation
  test_3_functions_triggers.py     16   all triggers, functions, procedures
  test_4_api_sql.py                31   CRUD via API, filters, every report query, dashboard
  test_5_auth_rbac.py              19   login, JWT, 403s, database-level privilege enforcement
  test_6_mongo_and_integration.py   9   validator, CRUD, $push/$pull, ack, aggregation, SQL↔Mongo
  test_7_viewer_role.py            22   viewer can read, cannot write (API 403 + PostgreSQL permission denied)
```

## 9. Evaluation Rubric – Completion Status

| # | Component | Marks | Status | Evidence |
|---|---|---:|---|---|
| 1 | ER diagram | 2 | ✅ Complete | `docs/er_diagram.png` |
| 2 | Relational schema with keys, relationships, constraints | 3 | ✅ Complete | `docs/relational_schema.png`, §5.1 |
| 3 | SQL implementation – DDL with constraints | 4 | ✅ Complete | `01_schema.sql`: PK, FK (CASCADE/RESTRICT), UNIQUE, CHECK, NOT NULL, DEFAULT, ALTER, indexes |
| 4 | NoSQL database creation | 4 | ✅ Complete | 3 collections with `$jsonSchema` validators and 10 indexes (`mongo_setup.py`, `mongo_commands.js`) |
| 5 | Technology justification | 1 | ✅ Complete | §4 |
| 6 | DML operations | 4 | ✅ Complete | §5.3, `06_dml_demo.sql` (one headed INSERT/UPDATE/DELETE per table), `mongo_dml_demo.js`, all CRUD forms in the UI |
| 7 | Nested / correlated / recursive and JOIN queries | 4 | ✅ Complete | §5.4, 20 SQL queries + 5 MongoDB pipelines in Query Lab |
| 8 | Procedures/functions, triggers, CTE | 6 | ✅ Complete | 4 functions, 2 procedures, 5 triggers (4 trigger functions), 1 CTE + 2 recursive CTEs; every one run in `07_advanced_sql_demo.sql` (§5.5) |
| 9 | NoSQL features – RUD | 7 | ✅ Complete | find with filters/sort/text search, updateOne/$push/$pull/$addToSet, deleteOne/deleteMany, aggregation with $group/$lookup/$unwind/$facet |
| 10 | Next.js interface | 3 | ✅ Complete | 10 required pages + Query Lab, search/filter/sort, validation, confirmation dialogs, status badges |
| 11 | Backend/API and DB integration | 2 | ✅ Complete | FastAPI connected to both real servers, SQL↔Mongo integration |
| 12 | Authentication (frontend) + ≥2 roles + RBAC in database | 4 | ✅ Complete | login/logout, JWT, 3 roles `gs_admin` / `gs_security` / `gs_viewer` with GRANTs incl. column-level, `SET LOCAL ROLE` |
| 13 | Documentation, Git/GitHub | 2 | ✅ Complete | README.md, this report, GitHub repository |
| 14 | Originality, individual contribution, viva | 4 | ⏳ Team | demonstrated during viva |

### Notes on the design (differences from the diagrams, with reasons)
1. PostgreSQL table names are lowercase (`access_logs`, not `"Access_Logs"`). PostgreSQL folds unquoted identifiers to lowercase, and quoted mixed-case names would have to be quoted in every query. MongoDB collections keep the diagram names.
2. R8 lists both `alert_type` and `alerstype`. We treated `alerstype` as a typo, so there is a single `alert_type` field.
3. MongoDB documents contain the attributes from the schema plus a few extra fields (`location`, `tags`, `acknowledged`, `recipients`, `severity`) to show nested documents and arrays. All schema attributes are required by the validators.
4. No extra *users* table is added: application users are PostgreSQL login roles, which keeps the design at exactly 5 SQL tables + 3 collections.
5. Total participation on the "one" side of generates/at (every card or gate has a scan) is not enforced, because a newly issued card or new gate cannot have scans yet. It is enforced for the Employees–Cards relationship.
