# Test Report

**Run date:** 2026-11-17

| Test/check | Result | Evidence and limits |
|---|---|---|
| Backend unit suite | PASS: 13 passed | `python -m pytest tests/test_backend.py -q` from `backend/`; isolated in-memory SQLite |
| Seven synthetic correlation scenarios | PASS | Unit suite covers normal entry, tailgating, unauthorized entry, multiple entries, low-confidence filtering and investigation workflows |
| Deferred audit transaction behavior | PASS | A focused test confirms a non-committed audit row rolls back with its caller transaction |
| PostgreSQL schema/functions/procedures/triggers | PASS | PostgreSQL 16.15 disposable database; scripts `01`–`06` executed and updated scripts `03`, `05`, `07` re-applied |
| PostgreSQL runtime role/procedure path | PASS | Runtime login set `gg_security`, finalized a two-crossing synthetic session, and observed a CRITICAL incident plus PENDING outbox event; transaction rolled back |
| PostgreSQL RBAC negative/positive checks | PASS | Security direct outbox INSERT and DELETE denied; auditor UPDATE denied and SELECT succeeded; controlled outbox enqueue and audit-writer functions executed |
| Qdrant model integration | PASS: 1 passed | Qdrant 1.14.1 + qdrant-client 1.15.1; real all-MiniLM-L6-v2 384-dimensional normalized embedding, upsert, payload update/filter, semantic retrieval and deletion |
| Qdrant persistent storage | PASS | Model-backed point/vector retrieved after Qdrant process restart against the same storage path, then deleted |
| Frontend lint | PASS | `npm run lint`, no warnings or errors |
| Frontend TypeScript | PASS | `npx tsc --noEmit` |
| Frontend production build | PASS | `npm run build`; Next.js completed compile, lint/type validation, static generation and trace collection |
| Local demo outbox and semantic retrieval | PASS | All 11 seeded outbox events completed in Qdrant; a natural-language query returned 8 cosine-ranked results |
| Browser capture | PASS | Admin overview, incident queue and semantic-search screenshots are in `screenshots/` |
| Docker Compose configuration | PASS | Syntax-only validation with placeholder required environment variables |
| Docker Compose service startup | NOT VERIFIED | Docker Desktop engine is unavailable |

## Environment and scope

PostgreSQL checks were run only against dedicated disposable WSL databases, including a fresh bootstrap database. The real-model test used the preinstalled CPU PyTorch runtime with a session-local matching torchaudio wheel; no global Python package was changed. The browser demo used isolated SQLite with Qdrant 1.14.1 and the actual Sentence Transformers model. The Docker image build, container startup and Compose health checks remain unverified.

The Qdrant integration uses synthetic incident text and does not represent live camera input. The system does not use facial recognition.
