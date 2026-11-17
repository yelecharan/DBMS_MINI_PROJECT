"""PostgreSQL + MongoDB connectivity and structure."""
from app.db import ping_mongo, ping_postgres


def test_postgres_connection():
    assert "PostgreSQL 18" in ping_postgres()


def test_mongodb_connection():
    assert ping_mongo()["ok"] == 1.0


def test_five_sql_tables_exist(su):
    names = {r[0] for r in su.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")}
    assert {"employees", "cards", "gates", "access_logs", "incidents"} <= names


def test_foreign_keys_defined(su):
    fks = {r[0] for r in su.execute(
        "SELECT conname FROM pg_constraint WHERE contype = 'f'")}
    assert {"fk_cards_employee", "fk_logs_card", "fk_logs_gate", "fk_incidents_scan"} <= fks


def test_three_mongo_collections_with_validators(mdb):
    infos = {c["name"]: c for c in mdb.list_collections()}
    for name in ("Observations", "Report", "Alerts"):
        assert name in infos
        assert "$jsonSchema" in infos[name]["options"]["validator"]


def test_mongo_indexes(mdb):
    assert "uq_obs_id" in mdb.Observations.index_information()
    assert "txt_report_description" in mdb.Report.index_information()
    assert "idx_alert_status_time" in mdb.Alerts.index_information()


def test_health_endpoint(client):
    body = client.get("/api/health").json()
    assert body["postgres"].startswith("PostgreSQL")
    assert body["mongodb"].startswith("UP")


def test_seed_data_present(su, mdb):
    assert su.execute("SELECT COUNT(*) FROM employees").fetchone()[0] >= 10
    assert su.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] >= 1
    assert mdb.Alerts.count_documents({}) >= 1
