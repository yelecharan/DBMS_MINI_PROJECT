-- ==========================================
-- TAILGATING DETECTION AND ACCESS CONTROL
-- DATABASE SCHEMA
-- ==========================================

-- 1. EMPLOYEES TABLE
CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(100),
    designation VARCHAR(100),
    status VARCHAR(20) DEFAULT 'Active'
        CHECK (status IN ('Active', 'Inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. ACCESS CARDS TABLE
CREATE TABLE access_cards (
    card_id SERIAL PRIMARY KEY,
    employee_id INT UNIQUE NOT NULL,
    card_number VARCHAR(50) UNIQUE NOT NULL,
    issue_date DATE DEFAULT CURRENT_DATE,
    card_status VARCHAR(20) DEFAULT 'Active'
        CHECK (card_status IN ('Active', 'Blocked', 'Expired')),

    CONSTRAINT fk_card_employee
        FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id)
);

-- 3. ACCESS LOGS TABLE
CREATE TABLE access_logs (
    log_id SERIAL PRIMARY KEY,
    card_id INT NOT NULL,
    access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_type VARCHAR(10) NOT NULL
        CHECK (access_type IN ('Entry', 'Exit')),
    access_result VARCHAR(20) NOT NULL
        CHECK (access_result IN ('Granted', 'Denied')),
    location VARCHAR(100),

    CONSTRAINT fk_log_card
        FOREIGN KEY (card_id)
        REFERENCES access_cards(card_id)
);

-- 4. TAILGATING INCIDENTS TABLE
CREATE TABLE tailgating_incidents (
    incident_id SERIAL PRIMARY KEY,
    log_id INT,
    incident_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    severity VARCHAR(20) DEFAULT 'Medium'
        CHECK (severity IN ('Low', 'Medium', 'High')),
    incident_status VARCHAR(20) DEFAULT 'Open'
        CHECK (incident_status IN ('Open', 'Investigating', 'Resolved')),
    
    CONSTRAINT fk_incident_log
        FOREIGN KEY (log_id)
        REFERENCES access_logs(log_id)
);

-- 5. USERS TABLE
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(30) NOT NULL
        CHECK (role IN ('Admin', 'Security Officer')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);