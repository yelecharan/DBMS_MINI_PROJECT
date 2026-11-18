-- =====================================================================
-- GateSentry - Tailgating Detection System
-- 01_schema.sql : DDL for the 5 PostgreSQL relations (R1..R5)
-- Run while connected to the "gatesentry" database.
-- =====================================================================

-- ---------- DROP TABLE (clean re-creation, child tables first) ----------
DROP TABLE IF EXISTS incidents   CASCADE;
DROP TABLE IF EXISTS access_logs CASCADE;
DROP TABLE IF EXISTS gates       CASCADE;
DROP TABLE IF EXISTS cards       CASCADE;
DROP TABLE IF EXISTS employees   CASCADE;

-- ---------------------------------------------------------------------
-- R1 Employees(emp_id PK, name, department, phone)
-- ---------------------------------------------------------------------
CREATE TABLE employees (
    emp_id      SERIAL       PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    department  VARCHAR(50)  NOT NULL,
    phone       VARCHAR(15)  NOT NULL,
    CONSTRAINT uq_employees_phone  UNIQUE (phone),
    CONSTRAINT chk_employees_phone CHECK (phone ~ '^\+?[0-9]{10,13}$'),
    CONSTRAINT chk_employees_name  CHECK (length(trim(name)) >= 2)
);

-- ---------------------------------------------------------------------
-- R2 Cards(card_id PK, emp_id FK -> Employees, card_no, issue_date, expiry_date, status)
-- Employees (1) --has-- (N) Cards, total participation on both sides:
--   * every card belongs to an employee  -> emp_id NOT NULL
--   * every employee owns >= 1 card      -> deferred constraint trigger (02 file)
-- ---------------------------------------------------------------------
CREATE TABLE cards (
    card_id      SERIAL      PRIMARY KEY,
    emp_id       INT         NOT NULL,
    card_no      VARCHAR(20) NOT NULL,
    issue_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
    expiry_date  DATE        NOT NULL,
    status       VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_cards_employee FOREIGN KEY (emp_id)
        REFERENCES employees(emp_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uq_cards_card_no  UNIQUE (card_no),
    CONSTRAINT chk_cards_status  CHECK (status IN ('ACTIVE','INACTIVE','EXPIRED','LOST')),
    CONSTRAINT chk_cards_dates   CHECK (expiry_date > issue_date)
);

-- ---------------------------------------------------------------------
-- R3 Gates(gate_id PK, gate_name, location, type, status)
-- ---------------------------------------------------------------------
CREATE TABLE gates (
    gate_id    SERIAL       PRIMARY KEY,
    gate_name  VARCHAR(50)  NOT NULL,
    location   VARCHAR(100) NOT NULL,
    type       VARCHAR(15)  NOT NULL DEFAULT 'ENTRY',
    status     VARCHAR(12)  NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT uq_gates_name    UNIQUE (gate_name),
    CONSTRAINT chk_gates_type   CHECK (type IN ('ENTRY','EXIT','BIDIRECTIONAL')),
    CONSTRAINT chk_gates_status CHECK (status IN ('ACTIVE','INACTIVE','MAINTENANCE'))
);

-- ---------------------------------------------------------------------
-- R4 Access_Logs(scan_id PK, card_id FK -> Cards, gate_id FK -> Gates, scan_time, access_result)
-- Cards (1) --generates-- (N) Access_Logs, Gates (1) --at-- (N) Access_Logs.
-- Every log needs a card and a gate (total participation of Access_Logs) -> NOT NULL.
-- ON DELETE CASCADE: deleting a card or gate also deletes its scans (and their incidents).
-- ---------------------------------------------------------------------
CREATE TABLE access_logs (
    scan_id        SERIAL      PRIMARY KEY,
    card_id        INT         NOT NULL,
    gate_id        INT         NOT NULL,
    scan_time      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    access_result  VARCHAR(10) NOT NULL DEFAULT 'GRANTED',
    CONSTRAINT fk_logs_card FOREIGN KEY (card_id)
        REFERENCES cards(card_id) ON DELETE CASCADE,
    CONSTRAINT fk_logs_gate FOREIGN KEY (gate_id)
        REFERENCES gates(gate_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- R5 Incidents(incident_id PK, scan_id FK -> Access_Logs, detected_time, severity, status)
-- Access_Logs (1) --detects-- (N) Incidents; every incident comes from a scan -> NOT NULL.
-- ---------------------------------------------------------------------
CREATE TABLE incidents (
    incident_id    SERIAL      PRIMARY KEY,
    scan_id        INT         NOT NULL,
    detected_time  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    severity       VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
    status         VARCHAR(15) NOT NULL DEFAULT 'OPEN',
    CONSTRAINT fk_incidents_scan FOREIGN KEY (scan_id)
        REFERENCES access_logs(scan_id) ON DELETE CASCADE
);

-- ---------- ALTER TABLE (constraints added after creation) ----------
ALTER TABLE access_logs
    ADD CONSTRAINT chk_logs_result CHECK (access_result IN ('GRANTED','DENIED'));

ALTER TABLE incidents
    ADD CONSTRAINT chk_incidents_severity CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    ADD CONSTRAINT chk_incidents_status   CHECK (status IN ('OPEN','INVESTIGATING','RESOLVED','FALSE_ALARM'));

-- ---------- Indexes (FK columns + frequent filters) ----------
CREATE INDEX idx_cards_emp          ON cards(emp_id);
CREATE INDEX idx_logs_card          ON access_logs(card_id);
CREATE INDEX idx_logs_gate_time     ON access_logs(gate_id, scan_time);
CREATE INDEX idx_incidents_scan     ON incidents(scan_id);
CREATE INDEX idx_incidents_status   ON incidents(status);
CREATE INDEX idx_employees_dept     ON employees(department);
