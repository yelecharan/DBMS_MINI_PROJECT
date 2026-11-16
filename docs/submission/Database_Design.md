# Database Design

GateSentry keeps operational records in PostgreSQL. UUID primary keys identify entities. Foreign keys express ownership and audit relationships. Timestamps use timezone-aware values. Unique constraints protect emails, employee/gate/camera codes, badge hashes, and optional external event IDs. Check constraints in the SQL DDL constrain roles, statuses, directions, confidence and nonnegative counts. Indexes support gate/time event correlation and incident filtering.

## Entity inventory

| Entity | Purpose and key relationships |
|---|---|
| users | Authenticated actors; assigned to incidents and incident actions |
| employees | Workforce identity; owns credentials |
| sites | Physical locations; contains zones |
| zones | Hierarchy within a site; contains gates |
| gates | Entry/exit point; anchors events, sessions, cameras, incidents and rules |
| cameras | Camera metadata associated with a gate |
| access_credentials | Credential hash and validity belonging to an employee |
| access_events | Granted/denied badge activity at a gate |
| gate_sessions | Correlation window for badge events and observations |
| camera_observations | Anonymous tracker ID, direction, confidence and evidence reference |
| incidents | Correlation result, risk, severity, status and explanation |
| incident_actions | Investigation history and actor |
| evidence_assets | Privacy-aware evidence references, checksum and retention |
| audit_logs | Actor, entity, operation, before/after values and time |
| detection_rules | Threshold and session parameters, optionally gate-scoped |
| incident_vector_outbox | Transactional incident snapshot events, retries, lease state and Qdrant synchronization status |

See [ER_Diagram.mmd](ER_Diagram.mmd). The Python ORM uses string UUID values for SQLite portability and maps them to native PostgreSQL UUID columns.

## Consistency and privacy

Badge and observation ingestion is idempotent using `external_event_id`. Incident creation, audit event and vector-outbox snapshot share the PostgreSQL transaction. Status changes and their vector snapshots are committed together; the worker retries Qdrant independently. Qdrant upserts are idempotent by incident ID. Video is not stored by the application; references should point to redacted or policy-approved evidence with explicit retention. Tracker identifiers are anonymous and short-lived. Facial recognition is out of scope. Demo observations are synthetic and must be labeled as such.

## Database routines

The SQL folder provides risk/statistics/hierarchy functions, a security-definer `finalize_gate_session` procedure, protected audit/outbox functions, timestamp/audit triggers, read views, and query examples. PostgreSQL 16.15 validation succeeded on a disposable database. `01_schema_ddl.sql` is destructive and belongs only in PostgreSQL's one-time initialization flow on an empty data volume. For existing databases, back up first and use the additive migration/role procedure documented in [SQL_Commands_Reference.md](SQL_Commands_Reference.md).
