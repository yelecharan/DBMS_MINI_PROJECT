# SQL Commands Reference

Fresh database initialization is applied by Docker Compose in this order:

| Script | Content |
|---|---|
| `01_schema_ddl.sql` | Extensions, tables, constraints, indexes and views |
| `02_functions.sql` | Risk, gate statistics and zone hierarchy functions |
| `03_procedures.sql` | Gate-session finalization and protected audit/outbox functions |
| `04_triggers.sql` | Updated timestamp and incident audit triggers |
| `05_roles_permissions.sql` | Safe-to-rerun `gg_admin`, `gg_security`, `gg_auditor` and audit-writer grants |
| `06_runtime_roles.sql` | Creates separate API/worker login roles from `APP_DB_PASSWORD` and `WORKER_DB_PASSWORD` environment variables |
| `06_advanced_queries.sql` | DML, joins, nested/correlated queries, recursive and analytical CTE examples |
| `07_vector_outbox_migration.sql` | Additive outbox, constraint, function and procedure migration for an existing schema |

`01_schema_ddl.sql` contains `DROP` statements. It is only run on a new, empty PostgreSQL data volume by the one-time image initialization mechanism. Never re-run it against a database with data to preserve.

For an existing schema, take a verified backup. As the database owner, reapply `03_procedures.sql`, then `05_roles_permissions.sql`, then `07_vector_outbox_migration.sql`; set `APP_DB_PASSWORD` and `WORKER_DB_PASSWORD` in the shell and run `06_runtime_roles.sql` last. The migration checks for duplicate non-null incident session IDs before adding its unique constraint and raises an explicit error if cleanup is required.

These paths were validated against PostgreSQL 16.15 using a dedicated disposable database. Role checks confirmed the auditor is read-only, security cannot directly write the outbox or audit log, and controlled database functions support incident finalization/audit/outbox writes.

Examples (adapt database/user names to the local environment):

```sql
SELECT calculate_incident_risk_score(1, 0.90, 5, 0);
SELECT * FROM get_gate_incident_statistics(NULL, CURRENT_DATE - 30, CURRENT_DATE);
SELECT * FROM get_zone_hierarchy();
CALL finalize_gate_session('00000000-0000-0000-0000-000000000001');
SELECT * FROM v_incident_investigation_summary;
```

Use transactions for related event/session/incident changes. For role permissions, use the backend login created by `06_runtime_roles.sql`; do not connect the API as PostgreSQL superuser. The worker login defaults to `gg_admin` and is separate from the API login.
