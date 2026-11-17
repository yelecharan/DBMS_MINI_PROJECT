"""Create / reset the GateSentry databases on the REAL local servers.

    python -m scripts.init_db            (run from the backend/ folder)

PostgreSQL : creates database `gatesentry`, runs database/postgres/01..04 sql files,
             creates the login roles (admin, guard, gatesentry_app).
MongoDB    : creates database `gatesentry` with collections Observations, Report,
             Alerts (validators + indexes) and inserts sample documents that
             reference the PostgreSQL incidents by incident_id.
If a server is unreachable the script stops with the connection error - it never
falls back to any substitute database.
"""
import sys
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg import sql
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import PROJECT_DIR, settings          # noqa: E402
from app.mongo_setup import ALERTS, OBSERVATIONS, REPORT, create_collections  # noqa: E402
from app.utils import new_id                          # noqa: E402

SQL_DIR = PROJECT_DIR / "database" / "postgres"
SQL_FILES = ["01_schema.sql", "02_functions_triggers.sql", "03_roles.sql", "04_seed.sql"]


def su_connect(dbname: str) -> psycopg.Connection:
    return psycopg.connect(host=settings.PG_HOST, port=settings.PG_PORT, dbname=dbname,
                           user=settings.PG_SUPERUSER, password=settings.PG_SUPERUSER_PASSWORD,
                           autocommit=True)


def setup_postgres() -> list[dict]:
    db = settings.PG_DATABASE
    with su_connect("postgres") as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
            print(f"[pg] created database {db}")
        else:
            print(f"[pg] database {db} already exists - schema will be re-created")

    with su_connect(db) as conn:
        for f in SQL_FILES[:3]:
            conn.execute((SQL_DIR / f).read_text(encoding="utf-8"))
            print(f"[pg] executed {f}")

        # ---- login roles (passwords hashed by PostgreSQL with SCRAM-SHA-256) ----
        def upsert_login(user: str, password: str, extra: str = "") -> None:
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {} " + extra).format(
                sql.Identifier(user), sql.Literal(password)))

        upsert_login(settings.PG_APP_USER, settings.PG_APP_PASSWORD, "NOINHERIT")
        upsert_login(settings.DEMO_ADMIN_USER, settings.DEMO_ADMIN_PASSWORD)
        upsert_login(settings.DEMO_SECURITY_USER, settings.DEMO_SECURITY_PASSWORD)

        ident = sql.Identifier
        conn.execute(sql.SQL("GRANT gs_admin, gs_security TO {} WITH INHERIT FALSE, SET TRUE")
                     .format(ident(settings.PG_APP_USER)))
        conn.execute(sql.SQL("GRANT gs_admin TO {}").format(ident(settings.DEMO_ADMIN_USER)))
        conn.execute(sql.SQL("GRANT gs_security TO {}").format(ident(settings.DEMO_SECURITY_USER)))
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(ident(db)))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}, {}").format(
            ident(db), ident(settings.PG_APP_USER), ident(settings.DEMO_ADMIN_USER),
            ident(settings.DEMO_SECURITY_USER)))
        print("[pg] login roles ready:", settings.DEMO_ADMIN_USER, settings.DEMO_SECURITY_USER,
              settings.PG_APP_USER)

        conn.execute((SQL_DIR / SQL_FILES[3]).read_text(encoding="utf-8"))
        print("[pg] executed 04_seed.sql")

        cur = conn.execute("""
            SELECT i.incident_id, i.scan_id, i.detected_time, i.severity, i.status,
                   a.gate_id, g.gate_name, fn_authorized_count(i.scan_id) AS auth
            FROM incidents i JOIN access_logs a ON a.scan_id = i.scan_id
            JOIN gates g ON g.gate_id = a.gate_id ORDER BY i.incident_id""")
        cols = [c.name for c in cur.description]
        incidents = [dict(zip(cols, r)) for r in cur.fetchall()]
        for t in ["employees", "cards", "gates", "access_logs", "incidents"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"[pg]   {t:<12} {n} rows")
        return incidents


EXCESS = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 5}
METHODS = ["MANUAL_HEADCOUNT", "GUARD_PATROL", "TURNSTILE_COUNTER", "SIMULATED"]


def setup_mongo(incidents: list[dict]) -> None:
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000, tz_aware=True)
    client.admin.command("ping")                       # fail loudly if server is down
    db = client[settings.MONGO_DB]
    create_collections(db, drop_existing=True)
    print(f"[mongo] collections created in '{settings.MONGO_DB}':", db.list_collection_names())

    observations, reports, alerts = [], [], []
    for k, inc in enumerate(incidents):
        auth = max(int(inc["auth"]), 1)
        observed = auth + EXCESS[inc["severity"]]
        t = inc["detected_time"].astimezone()   # naive local PG time -> aware for MongoDB
        observations.append({
            "obs_id": new_id("OBS"), "incident_id": inc["incident_id"],
            "method": METHODS[k % len(METHODS)],
            "observed_count": observed, "authorized_count": auth,
            "timestamp": t - timedelta(minutes=1),
            "location": {"gate_id": inc["gate_id"], "gate_name": inc["gate_name"],
                         "scan_id": inc["scan_id"]},
            "observed_by": settings.DEMO_SECURITY_USER,
            "notes": f"{observed} people passed {inc['gate_name']} on {auth} authorised scan(s).",
            "tags": ["tailgating", inc["severity"].lower()],
        })
        if inc["status"] != "OPEN":
            reports.append({
                "report_id": new_id("RPT"), "incident_id": inc["incident_id"],
                "description": (f"Guard confirmed {observed - auth} unauthorised person(s) "
                                f"following a card holder through {inc['gate_name']}. "
                                f"Incident marked {inc['status'].replace('_', ' ').lower()}."),
                "reported_by": {"username": settings.DEMO_SECURITY_USER, "role": "security"},
                "attachments": [{"file_name": f"incident_{inc['incident_id']}_logbook.pdf",
                                 "file_type": "application/pdf",
                                 "note": "Scanned guard logbook page"}],
                "timestamp": t + timedelta(minutes=30),
            })
        pending = inc["status"] in ("OPEN", "INVESTIGATING")
        alerts.append({
            "alert_id": new_id("ALT"), "incident_id": inc["incident_id"], "alert_time": t,
            "alert_type": "ESCALATION" if inc["severity"] == "CRITICAL" else "TAILGATING",
            "severity": inc["severity"],
            "message": f"{inc['severity']} tailgating suspected at {inc['gate_name']} "
                       f"(scan #{inc['scan_id']}).",
            "ack_status": "PENDING" if pending else "ACKNOWLEDGED",
            "acknowledged": None if pending else {"by": settings.DEMO_SECURITY_USER,
                                                  "at": t + timedelta(minutes=10),
                                                  "comment": "Checked on site"},
            "recipients": ["security-desk", "facility-admin"],
        })

    db[OBSERVATIONS].insert_many(observations)
    db[REPORT].insert_many(reports)
    db[ALERTS].insert_many(alerts)
    for c in (OBSERVATIONS, REPORT, ALERTS):
        print(f"[mongo]   {c:<12} {db[c].count_documents({})} documents")


if __name__ == "__main__":
    try:
        incs = setup_postgres()
    except psycopg.OperationalError as exc:
        sys.exit(f"PostgreSQL connection failed: {exc}")
    try:
        setup_mongo(incs)
    except Exception as exc:                      # noqa: BLE001
        sys.exit(f"MongoDB setup failed ({settings.MONGO_URI}): {exc}")
    print("Done. Open pgAdmin -> gatesentry, and MongoDB Compass -> gatesentry.")
