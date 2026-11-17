# GateSentry
## Explainable, Privacy-First Office Tailgating Detection and Incident Intelligence System

### 1. Title

GateSentry — an explainable system that correlates employee badge events with anonymous camera crossing observations to identify possible tailgating and unauthorized entry.

### 2. Students SRN and Name

- [STUDENT NAME] — [STUDENT SRN]
- [TEAM MEMBER DETAILS]

### 3. Abstract

GateSentry correlates authorized badge events with confidence-filtered, anonymous person-crossing observations at office gates. When observed crossings exceed authorized entries, it creates an incident with counts, a risk score, severity and an explanation. Security staff can investigate incidents, record actions and resolve or classify a false positive. Auditors can inspect history. PostgreSQL stores relational and audit records; Qdrant is intended for semantic incident retrieval. The system does not use facial recognition. Sample observations are synthetic demo inputs and do not represent live CCTV inference.

### 4. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| API | FastAPI, Pydantic |
| Relational database | PostgreSQL target; SQLite used in existing isolated tests |
| ORM | SQLAlchemy |
| Authentication | JWT, Argon2 |
| Vector database | Qdrant 1.14.x; persistent 384-dimensional COSINE collection |
| Embedding | Sentence Transformers `all-MiniLM-L6-v2`, normalized CPU embeddings |
| Synchronization | PostgreSQL transactional outbox and retrying worker |

### 5. SQL Database Commands

Scripts in `backend/database/sql/` define the relational schema, functions, procedure, triggers, role grants, runtime logins, additive migration and example queries. PostgreSQL 16.15 execution was verified against a dedicated disposable database. See [SQL_Commands_Reference.md](SQL_Commands_Reference.md) and [Database_Design.md](Database_Design.md). `01_schema_ddl.sql` contains DROP statements and runs only on a fresh PostgreSQL data volume.

### 6. NoSQL/Vector Database Commands

The `incident_embeddings` Qdrant collection is configured for 384-dimensional cosine similarity. The model-backed integration verified upsert, retrieval, payload update, filtered semantic search and deletion. A real embedding was recovered after a Qdrant restart using the same storage directory. See [Qdrant_Commands_Reference.md](Qdrant_Commands_Reference.md).

Incident creation/status changes enqueue vector snapshots in the same PostgreSQL transaction. A separate worker processes pending events with leases, bounded retries and idempotent Qdrant upserts; model failures are visible in the outbox rather than replaced by synthetic vectors.

### 7. Next.js Project Tree Structure

```text
frontend/src/
  app/
    (auth)/login/
    (dashboard)/
      overview/ monitoring/ incidents/ incidents/[id]/ intelligence/
      employees/ gates/ users/ audit/ reports/ demo/
  components/layout/
  components/ui/
  context/AuthContext.tsx
  types/index.ts
```

### 8. Sample Screenshots of Application Code and Demo

Genuine browser screenshots are stored in [screenshots/](screenshots/): the [overview](screenshots/overview.png), [incident queue](screenshots/incidents.png) and [semantic vector search](screenshots/vector-intelligence.png). They show the local application with synthetic seed data; they are not production CCTV evidence. The demo used isolated SQLite and a running Qdrant server, not the unverified Docker Compose stack.

### 9. Evaluation Rubrics — Completion Status

See [Rubric_Mapping.md](Rubric_Mapping.md) for evidence per criterion. See [Test_Report.md](Test_Report.md) for observed verification results: 13 backend unit tests, PostgreSQL 16.15 schema/role/procedure checks, model-backed Qdrant semantic CRUD and persistence, frontend lint/typecheck and a production build pass. Docker Compose container startup remains unverified because Docker Desktop is unavailable. Student names/SRNs/institution details remain placeholders because those details were not provided.

## Verification and limitations

Backend unit tests use in-memory SQLite. Separate PostgreSQL checks used only the named disposable validation database. The Qdrant integration used Qdrant 1.14.1 and actual Sentence Transformers embeddings. Docker Compose configuration was syntax-checked, but Docker Desktop was unavailable for container startup. Development secrets are generated per process when omitted; production requires explicit `SECRET_KEY` and `DETECTOR_API_KEY`. The nested Git repository has no commits or configured remote; publication status is recorded in `GITHUB_FILE_AUDIT.md`.
