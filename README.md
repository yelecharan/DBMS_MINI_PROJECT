# GateSentry – Tailgating Detection DBMS

A database-driven tailgating management system built as a DBMS mini project.
An employee scans an authorised access card at a secured gate. If a guard sees **more people walk through than the number of authorised scans**, a suspected tailgating incident is recorded, with observations, reports and alerts.

> No CCTV, computer vision or machine learning. Observations are entered by hand or simulated.

| | |
|---|---|
| **Students** | Vilohith Sree Sai Reddy Daggolu (PES1UG24CS535) · Yele Charan (PES1UG25CS856) |
| **SQL** | PostgreSQL 18, 5 relations: `employees`, `cards`, `gates`, `access_logs`, `incidents` |
| **NoSQL** | MongoDB 9 Community Server, 3 collections: `Observations`, `Report`, `Alerts` |
| **Backend** | Python FastAPI, SQLAlchemy + psycopg 3, PyMongo, JWT |
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS 4 |
| **GUIs** | pgAdmin 4 and MongoDB Compass |

The full university report is in [docs/REPORT.md](docs/REPORT.md). Diagrams are in [docs/er_diagram.png](docs/er_diagram.png) and [docs/relational_schema.png](docs/relational_schema.png).

---

## Architecture

```
Next.js (localhost:3000)  ──HTTP + JWT──▶  FastAPI (localhost:8000)
                                              │
                ┌─────────────────────────────┴──────────────────────────────┐
                ▼                                                            ▼
   PostgreSQL 18  db "gatesentry"                              MongoDB  db "gatesentry"
   employees, cards, gates,                                    Observations, Report, Alerts
   access_logs, incidents                                      (each document has incident_id ──▶ incidents)
   + triggers, functions, procedures, roles
```

* **Database-level RBAC.** Users are PostgreSQL login roles (`admin` ∈ `gs_admin`, `guard` ∈ `gs_security`, `viewer` ∈ `gs_viewer`). PostgreSQL stores their passwords as SCRAM-SHA-256 hashes and checks them at login. The API connects as `gatesentry_app`, which has **no privileges of its own**. Every request runs `SET LOCAL ROLE gs_admin | gs_security | gs_viewer`, so the GRANTs in `03_roles.sql` decide what a user can do, including the column-level `UPDATE(status)` grant on incidents.
* **Linking SQL and NoSQL.** MongoDB documents reference `incidents.incident_id`. The backend checks that the incident exists before it inserts a document. When an incident is deleted, the backend also deletes its MongoDB documents. Reporting tailgating writes the SQL incident and the MongoDB observation and alert inside one SQL transaction, so if MongoDB fails the incident is rolled back.

## Repository layout

```
DBMS/
├── README.md
├── .gitignore
├── database/
│   ├── postgres/
│   │   ├── 01_schema.sql              DDL: DROP/CREATE/ALTER TABLE, PK, FK, UNIQUE, CHECK, NOT NULL, DEFAULT, indexes
│   │   ├── 02_functions_triggers.sql  5 triggers, 4 functions (+4 trigger functions), 2 procedures
│   │   ├── 03_roles.sql               gs_admin / gs_security group roles and GRANTs
│   │   ├── 04_seed.sql                sample data (DML INSERT)
│   │   ├── 05_queries.sql             DML, JOINs, nested, correlated, recursive, GROUP BY/HAVING, CTEs
│   │   ├── 06_dml_demo.sql            demo: list/count tables, structure, view data, INSERT/UPDATE/DELETE
│   │   └── 07_advanced_sql_demo.sql   demo: calls every function/procedure, fires every trigger, CTEs (rolls back)
│   └── mongodb/
│       ├── mongo_commands.js          collection creation, validators, indexes, CRUD, aggregation
│       └── mongo_dml_demo.js          demo: list/count collections, structure, view data, insert/update/delete
├── backend/
│   ├── .env.example                   copy to .env (never committed)
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                    FastAPI app, auth routes, DB-error → HTTP mapping
│   │   ├── config.py  db.py  auth.py  deps.py  schemas.py  utils.py
│   │   ├── mongo_setup.py             $jsonSchema validators + indexes
│   │   └── routers/                   employees, cards, gates, access_logs, incidents,
│   │                                  observations, reports, alerts, analytics
│   ├── scripts/init_db.py             creates/resets both databases and loads sample data
│   └── tests/                         115 pytest tests against the real servers
├── frontend/                          Next.js app (tree in docs/REPORT.md §7)
└── docs/
    ├── REPORT.md                      university report
    ├── er_diagram.png  relational_schema.png
    ├── capture_screenshots.mjs        regenerates docs/screenshots with headless Edge
    └── screenshots/
```

## Running locally (Windows)

### Prerequisites
* PostgreSQL 18 running as a service (port 5432) with access to the `postgres` superuser password
* MongoDB Community Server running as a service (port 27017). MongoDB Compass alone is only the GUI and is not enough.
* Python 3.11+ and Node.js 20+

### 1. Backend and databases
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # then set PG_SUPERUSER_PASSWORD (and JWT_SECRET)
.venv\Scripts\python -m scripts.init_db
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
`init_db` creates the `gatesentry` database, tables, triggers, functions, roles and sample data in PostgreSQL. It also creates the three validated MongoDB collections and their documents. Running it again resets everything to the sample data. If either server can't be reached, it stops with the connection error and does not fall back to anything else.

API docs: http://localhost:8000/docs · Health check: http://localhost:8000/api/health

To switch to **MongoDB Atlas**, set `MONGO_URI=mongodb+srv://<user>:<password>@<cluster>/` in `backend/.env`.

### 2. Frontend
```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```
Open http://localhost:3000.

| Username | Password | Role |
|---|---|---|
| `admin` | `Admin@123` | Administrator (`gs_admin`): full CRUD on all tables and collections |
| `guard` | `Guard@123` | Security staff (`gs_security`): view, record scans and observations, write reports, update incident status, acknowledge alerts |
| `viewer` | `Viewer@123` | Viewer (`gs_viewer`): limited user, read-only everywhere and cannot see employee phone numbers (column-level GRANT) |

These are demo accounts. You can change them in `backend/.env` and then run `init_db` again.

### 3. Tests
```powershell
cd backend
.venv\Scripts\python -m pytest -v
```
The tests cover connectivity, constraints, triggers, functions and procedures, SQL CRUD, every report query, authentication, RBAC (API and database level), MongoDB CRUD and aggregation, and SQL↔MongoDB integration. They run against the real servers and clean up after themselves.

### 4. Demo scripts (view tables, insert, update, delete)
* **PostgreSQL:** in pgAdmin, right-click `gatesentry` → **Query Tool**, open `database/postgres/06_dml_demo.sql` and run it (F5). It lists the 5 tables, counts rows, shows each table's columns and constraints and all data, inserts into every table, runs UPDATE and DELETE, then shows the data again.
* **MongoDB:** in Compass, connect to `mongodb://localhost:27017` and click **Open MongoDB shell**. Run `use gatesentry`, then copy the commands in `database/mongodb/mongo_dml_demo.js` **one at a time** and press Enter after each. It covers the same steps for the 3 collections, with one headed insert, update and delete per collection.
* **Advanced SQL:** run `database/postgres/07_advanced_sql_demo.sql` the same way in pgAdmin. It calls every function and procedure, fires all 5 triggers (the rejections show in the **Messages** tab), and runs the CTEs, recursive CTEs, a view, window functions and a SAVEPOINT. It ends with `ROLLBACK`, so nothing is saved.
* Both scripts can be run more than once. To go back to the original sample data, run `python -m scripts.init_db` again.

### 5. Look at the data in the GUIs
* **pgAdmin 4:** Servers → PostgreSQL 18 → Databases → `gatesentry` → Schemas → public → Tables / Functions / Trigger Functions. Login/Group Roles show `admin`, `guard`, `viewer`, `gatesentry_app`, `gs_admin`, `gs_security`, `gs_viewer`.
* **MongoDB Compass:** connect to `mongodb://localhost:27017` → `gatesentry` → `Observations`, `Report`, `Alerts`. The Validation and Indexes tabs show the schemas and indexes. `database/mongodb/mongo_commands.js` can be pasted into Compass's built-in **MONGOSH** shell.
