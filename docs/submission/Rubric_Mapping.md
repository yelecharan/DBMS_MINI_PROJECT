# Evaluation Rubric Mapping (50 marks)

Status reflects repository inspection and the verification recorded in [Test_Report.md](Test_Report.md).

| Criterion | Marks | Implementation evidence | Status |
|---|---:|---|---|
| ER diagram | 2 | `ER_Diagram.mmd` and generated PNG | COMPLETE; includes relational entities and outbox |
| Relational schema, keys, relationships and constraints | 3 | `backend/database/sql/01_schema_ddl.sql`, ORM models | VERIFIED on PostgreSQL 16.15 disposable database |
| SQL DDL and constraints | 4 | Schema plus additive outbox migration | VERIFIED on fresh disposable database and migration re-application |
| NoSQL/Vector database | 4 | `vector_service.py`, Qdrant collection settings | VERIFIED with actual model-backed CRUD/search and persistence after restart |
| Technology justification | 1 | Database design and report | COMPLETE as documented rationale; verify against instructor expectations |
| DML | 4 | seed data, API services, `06_advanced_queries.sql` | VERIFIED on PostgreSQL 16.15 disposable database |
| Nested/correlated/recursive queries and joins | 4 | `06_advanced_queries.sql` | VERIFIED by successful PostgreSQL execution |
| Procedure, function, trigger and CTE | 6 | SQL scripts `02`–`07` | VERIFIED, including security-role finalization/outbox behavior |
| Vector CRUD/RUD feature | 7 | `vector_service.py`, model-backed Qdrant test | VERIFIED with actual semantic ranking and restart persistence |
| Next.js | 3 | `frontend/src/app/` pages | VERIFIED by lint, typecheck and production build |
| Backend/API and database integration | 2 | FastAPI routes and SQLAlchemy | Unit and PostgreSQL routine/role integration verified; Docker startup remains unverified |
| Frontend authentication and two roles with database RBAC | 4 | auth context, role dependencies, `SET LOCAL ROLE`, SQL grants | PostgreSQL role grants verified; full Docker-hosted browser authorization matrix remains |
| Documentation and Git/GitHub | 2 | `docs/`, nested Git | Documentation updated; publishing blocked because target repository API returns 404 and nested repo has no remote |
| Demonstration and testing | 2 | backend tests and demo route | 13 unit tests, semantic Qdrant test and PostgreSQL transaction checks pass; genuine screenshots pending |
| Originality and individual contribution | 4 | project content and Git history | NOT VERIFIED; student contribution and identity must be supplied, not inferred |

Total rubric: 50 marks. No score is claimed by this mapping.
