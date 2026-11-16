# API Documentation

FastAPI exposes interactive OpenAPI UI at `/docs` and ReDoc at `/redoc`; open these on a running backend. The root health endpoints are `/` and `/health`. API routes are mounted under `/api`.

| Route group | Function |
|---|---|
| auth | Login and current-user identity |
| employees | Employee list/create/update operations |
| gates | Gate list and management |
| access-events | Badge event ingestion/query |
| ingest | Camera observation ingestion |
| gate-sessions | Session inspection/finalization |
| incidents | Incident list/detail and status actions |
| investigations | Assignment, notes, resolution and false-positive workflow |
| vector | Incident vector CRUD and semantic search |
| analytics | Dashboard/report aggregations |
| demo | Synthetic scenario generation |
| audit | Audit record inspection |
| users | User administration |

Authentication uses an HttpOnly access-token cookie and accepts bearer JWTs for API clients. User roles are ADMIN, SECURITY_OFFICER and AUDITOR. Authenticated PostgreSQL transactions use `SET LOCAL ROLE` with a pool-safe role reset:

| Capability | Application/database role |
|---|---|
| User/gate/employee administration, outbox controls | ADMIN / `gg_admin` |
| Incident investigation, badge/camera ingestion and session finalization | SECURITY_OFFICER / `gg_security` |
| Read-only incident, audit and analytics access | AUDITOR / `gg_auditor` |
| Append immutable audit entries | Internal `gg_audit_writer` function capability; no direct audit-table writes |
| Background Qdrant synchronization | Separate `gatesentry_worker` login, defaulting to `gg_admin` |

Ingestion with a valid detector API key runs under the security database role. PostgreSQL database-role checks, including auditor write denial, security outbox denial and a security-role finalization procedure call, passed on a disposable PostgreSQL 16.15 database. Request and response schemas are in `backend/app/schemas/schemas.py`; route declarations are under `backend/app/api/routes/`.
