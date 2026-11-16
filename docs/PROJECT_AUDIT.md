# GateSentry Project Audit

**Audit date:** 2026-11-17
**Project root:** `AR_VR_1/AR_VR_1/GateSentry-DBMS-MiniProject`
**Scope:** existing GateSentry project only; the enclosing Space Debris repository was not modified.

## Verified status

| Area | Status | Evidence / remaining limitation |
|---|---|---|
| Project preservation | PASS | Existing backend, frontend and SQL implementation retained; no rebuild from scratch |
| Sentence Transformers | PASS | `all-MiniLM-L6-v2` loaded on CPU and generated normalized 384-dimensional vectors; no fake-embedding fallback |
| Qdrant semantic CRUD | PASS | Qdrant 1.14.1 and compatible `qdrant-client` 1.15.1; model-backed insertion, payload update/filter, natural-language semantic retrieval and deletion passed |
| Qdrant persistence | PASS | A real model-backed point and 384-dimensional vector were recovered after restarting Qdrant on the same storage directory |
| PostgreSQL schema/routines | PASS | PostgreSQL 16.15 disposable database; schema, functions, procedures, triggers, roles and advanced-query scripts executed; updated procedure, grants and additive migration re-applied successfully |
| PostgreSQL transaction/outbox | PASS | As the runtime security role, finalizing a synthetic session created a CRITICAL incident and PENDING outbox row in one transaction; the validation transaction was rolled back |
| PostgreSQL RBAC | PASS | Security access and controlled function permissions worked; direct outbox insertion, security deletion and auditor update were denied; auditor reads succeeded |
| Backend unit tests | PASS | `13 passed` using the in-memory SQLite test database |
| Frontend lint/typecheck/build | PASS | ESLint clean, `tsc --noEmit` clean, and production `next build` completed |
| Local outbox and semantic UI | PASS | Processed all 11 seeded outbox events into Qdrant; the live natural-language query returned 8 ranked matches |
| Browser workflows/screenshots | PASS | Admin login, overview, incident queue and semantic search verified; screenshots saved under `docs/submission/screenshots/` |
| Docker Compose configuration | PASS | Configuration syntax is checked with required placeholder variables |
| Docker Compose startup | NOT VERIFIED | Docker Desktop engine is unavailable in this environment |
| GitHub publication | BLOCKED | Nested repository has no commits or remote; GitHub API returns 404 for the configured outer repository target. Do not push to the unrelated outer repository |

## Implementation changes

- Uses the actual `sentence-transformers/all-MiniLM-L6-v2` model on CPU, checks dimension/normalization, and reports model failures explicitly.
- Persists incident creation/status changes and vector work through a transactional PostgreSQL outbox; an idempotent worker leases, retries, recovers expired work, and exposes admin retry/status endpoints.
- Maps authenticated API sessions to least-privilege PostgreSQL roles. A separate capability role appends immutable audit rows through a `SECURITY DEFINER` function; security officers and auditors receive no direct audit-table writes.
- Creates separate non-superuser API and worker database logins in the PostgreSQL first-boot flow. Demo seeding no longer drops schema, and reset is development/admin-only.
- Aligns the Qdrant client constraint with Qdrant 1.14.x and requires explicit production secrets.

## Environment notes

PostgreSQL validation used the dedicated disposable database `gatesentry_validation_20261117` in WSL Ubuntu. No production database was touched. Temporary validation login credentials and records were used only in that local database. The Qdrant validation server and model test environment live under the per-session storage directory, not in the project source.

The packaged Docker build/start sequence and container health checks remain unverified because Docker is unavailable. Browser evidence uses the isolated local SQLite demo and Qdrant server, with synthetic seed data; it does not demonstrate a Compose/PostgreSQL runtime. Student names/SRNs/institution details were not supplied and remain visibly marked as placeholders in the report packet.
