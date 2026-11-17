# Demo Guide

## Local setup

Copy `.env.example` to `.env`, replace every placeholder, then run `docker compose up --build`. On the first run the database scripts create the schema and runtime roles; later runs reuse the persistent volume. Open `http://localhost:3000`, API docs at `http://localhost:8000/docs`, and Qdrant at `http://localhost:6333`.

Development seed accounts:

- Admin: `admin@gatesentry.internal` / `AdminPassword2026!`
- Security officer: `security@gatesentry.internal` / `SecurityPassword2026!`
- Auditor: `auditor@gatesentry.internal` / `AuditorPassword2026!`

These credentials are for local demonstration only. Seeding only runs for an empty database and does not drop tables. The reset endpoint requires a development environment and an admin login.

Backend API docs: `http://localhost:8000/docs`. Frontend: `http://localhost:3000`.

## Explainable correlation scenarios

Use unique external event IDs and distinct anonymous tracker IDs per person. A crossing counts only when its confidence meets the gate threshold. Finalize the session and inspect counts, incident summary, risk score, severity, actions and audit entries.

| Scenario | Expected outcome |
|---|---|
| 1 badge + 1 confirmed crossing | NORMAL, no incident |
| 1 badge + 2 confirmed crossings | TAILGATING, one unmatched crossing |
| 0 badges + 1 confirmed crossing | UNAUTHORIZED_ENTRY |
| 2 badges + 2 confirmed crossings | NORMAL, no incident |
| 2 badges + 4 confirmed crossings | TAILGATING, two unmatched crossings |
| 1 confirmed + 1 below-threshold observation | NORMAL, low-confidence observation excluded |
| Mark generated incident false positive | FALSE_POSITIVE with explanatory note and audit/action record |

The backend test suite exercises all listed scenarios using isolated SQLite data. PostgreSQL 16.15 validation confirmed that security-role finalization can create an incident and outbox row transactionally. Demo-created observations are synthetic; there is no live CCTV inference pipeline or face recognition. Semantic search uses actual 384-dimensional Sentence Transformers vectors and requires model availability.
