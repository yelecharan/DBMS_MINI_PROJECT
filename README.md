# GateSentry

Explainable, privacy-first office tailgating detection and incident intelligence. GateSentry correlates employee badge events with anonymous person-crossing observations. Demo observations are synthetic; the application does not implement facial recognition or a live CCTV inference pipeline.

## Run with Docker Compose

1. Install Docker Desktop and start its engine.
2. Copy `.env.example` to `.env`. Replace every placeholder with unique, URL-safe secrets; do not commit `.env`.
3. Run `docker compose up --build` from this directory.
4. Open the dashboard at [http://localhost:3000](http://localhost:3000), API docs at [http://localhost:8000/docs](http://localhost:8000/docs), and Qdrant health at [http://localhost:6333/healthz](http://localhost:6333/healthz).

On a new PostgreSQL data volume, Compose applies the SQL schema, functions, procedures, triggers, role grants and runtime login setup in order. The initial DDL contains `DROP` statements and is mounted into PostgreSQL's one-time initialization directory; it runs only when the data volume is empty. Do not delete a populated volume to re-run initialization. Back up existing databases and follow the additive migration steps in [SQL_Commands_Reference.md](docs/submission/SQL_Commands_Reference.md).

The app and outbox worker use separate non-superuser PostgreSQL logins. API transactions map authenticated application roles to `gg_admin`, `gg_security` or `gg_auditor`; the auditor role is read-only. The worker uses its own `gg_admin`-mapped login to claim and update outbox rows.

## Local development

Backend (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-cpu.txt
$env:DATABASE_URL = "sqlite:///./gatesentry.db"
python -m uvicorn app.main:app --reload --port 8000
```

The CPU requirements pin matching PyTorch/torchaudio/torchvision versions. `all-MiniLM-L6-v2` downloads on first use and produces normalized 384-dimensional embeddings. If it cannot load, semantic operations report an explicit error; there is no token-hash fallback.

Frontend (Node 20+):

```powershell
cd frontend
npm ci
npm run dev
```

SQLite is intended for local development and unit tests; PostgreSQL is required to exercise SQL roles, routines and migrations. To run unit tests, use `backend/` as the working directory:

```powershell
python -m pytest tests/test_backend.py -q
```

To run model-backed Qdrant integration tests, start PostgreSQL/Qdrant or a Qdrant server, then set `QDRANT_URL` and run `python -m pytest tests/integration -m integration -q`. The Qdrant client is constrained to the server's supported minor-version range.

## Demo accounts and data safety

In development, an empty database is seeded with:

- `admin@gatesentry.internal` / `AdminPassword2026!`
- `security@gatesentry.internal` / `SecurityPassword2026!`
- `auditor@gatesentry.internal` / `AuditorPassword2026!`

These are demo-only credentials; change them before sharing a running instance. Seeding refuses non-empty databases and does not drop tables. The demo reset endpoint is restricted to development and administrator accounts.

For system design, SQL execution order and exact verification results, see [the project audit](docs/PROJECT_AUDIT.md), [the submission report](docs/submission/DBMS_Project_Report.md), and [the test report](docs/submission/Test_Report.md).

Genuine screenshots of the local synthetic-data demo are in [docs/submission/screenshots](docs/submission/screenshots/).
