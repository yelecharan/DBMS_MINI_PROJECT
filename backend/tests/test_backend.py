import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.session import Base
from app.models.models import (
    User, Employee, Site, Zone, Gate, Camera, AccessCredential,
    AccessEvent, GateSession, CameraObservation, Incident, IncidentAction, AuditLog,
    IncidentVectorOutbox
)
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.services.risk_engine import calculate_risk_score
from app.services.event_correlation import process_badge_swipe, ingest_person_crossing, finalize_gate_session_logic
from app.services.investigation_service import acknowledge_incident, assign_incident, resolve_incident, mark_incident_false_positive
from app.services.vector_service import EmbeddingUnavailableError, vector_service
from app.services.outbox_service import process_outbox_event, retry_failed_outbox_event
from app.services.audit_service import log_audit_event
from app.services.demo_service import (
    execute_scenario_normal_entry, execute_scenario_tailgating,
    execute_scenario_unauthorized_entry, execute_scenario_multiple_authorized,
    execute_scenario_multiple_tailgating, execute_scenario_low_confidence,
    execute_scenario_false_positive,
)

# Isolated Test Database
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_password_hashing_and_jwt():
    raw = "SecurePassword123!"
    h = hash_password(raw)
    assert h != raw
    assert verify_password(raw, h) is True
    assert verify_password("WrongPassword!", h) is False

    token = create_access_token(subject="user_123", role="ADMIN")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["role"] == "ADMIN"


def test_audit_log_can_join_the_callers_transaction(db_session):
    log_audit_event(
        db=db_session,
        entity_type="TEST",
        entity_id="transaction-check",
        action="CREATE",
        commit=False,
    )
    db_session.flush()
    assert db_session.query(AuditLog).filter_by(entity_id="transaction-check").count() == 1

    db_session.rollback()
    assert db_session.query(AuditLog).filter_by(entity_id="transaction-check").count() == 0


def test_risk_scoring_deterministic_formula():
    # Case: 1 unmatched, 0.90 confidence, 5 zone bonus, 0 repeats
    # Formula: (25 * 1) + (20 * 0.90) + 5 + 0 = 25 + 18 + 5 = 48.0 -> MEDIUM
    res1 = calculate_risk_score(unmatched_count=1, average_confidence=0.90, zone_sensitivity_bonus=5)
    assert res1.final_score == 48.0
    assert res1.severity == "MEDIUM"

    # Case: 2 unmatched, 0.95 confidence, 20 zone bonus, 2 repeats (10 bonus)
    # Formula: 50 + 19 + 20 + 10 = 99.0 -> CRITICAL
    res2 = calculate_risk_score(unmatched_count=2, average_confidence=0.95, zone_sensitivity_bonus=20, repeat_incident_count=2)
    assert res2.final_score == 99.0
    assert res2.severity == "CRITICAL"


def test_employee_and_access_credential_verification(db_session):
    emp = Employee(
        employee_code="EMP-TEST-01",
        full_name="Alice Smith",
        email="alice.test@example.com",
        department="Engineering",
        is_active=True
    )
    db_session.add(emp)
    db_session.flush()

    cred = AccessCredential(
        employee_id=emp.id,
        credential_hash="hash_badge_alice",
        status="ACTIVE"
    )
    db_session.add(cred)
    db_session.flush()

    site = Site(site_name="Test Site", address="123 Test St")
    db_session.add(site)
    db_session.flush()

    zone = Zone(site_id=site.id, zone_name="Engineering Zone", zone_type="OFFICE", sensitivity_level=5)
    db_session.add(zone)
    db_session.flush()

    gate = Gate(
        zone_id=zone.id,
        gate_code="GATE-T01",
        gate_name="Test Gate 01",
        direction="ENTRY",
        is_active=True,
        session_window_seconds=8,
        minimum_detection_confidence=0.65
    )
    db_session.add(gate)
    db_session.commit()

    # Valid swipe
    event, session = process_badge_swipe(
        db=db_session,
        gate_id=gate.id,
        credential_hash="hash_badge_alice",
        direction="ENTRY"
    )
    assert event.decision == "GRANTED"
    assert session is not None
    assert session.status == "OPEN"
    assert session.expected_authorized_entries == 1

    # Invalid swipe (bogus badge)
    event_bad, session_bad = process_badge_swipe(
        db=db_session,
        gate_id=gate.id,
        credential_hash="bogus_unknown_badge",
        direction="ENTRY"
    )
    assert event_bad.decision == "DENIED"
    assert session_bad is None


def test_scenario_tailgating_detection(db_session):
    site = Site(site_name="HQ", address="Address")
    db_session.add(site)
    db_session.flush()
    zone = Zone(site_id=site.id, zone_name="Lobby", zone_type="PERIMETER", sensitivity_level=10)
    db_session.add(zone)
    db_session.flush()
    gate = Gate(zone_id=zone.id, gate_code="G-01", gate_name="Main Turnstile", direction="ENTRY", session_window_seconds=8)
    db_session.add(gate)
    db_session.flush()
    cam = Camera(gate_id=gate.id, camera_code="C-01", camera_name="Overhead Cam")
    db_session.add(cam)
    emp = Employee(employee_code="E-1", full_name="Bob", email="bob@test.com", department="QA")
    db_session.add(emp)
    db_session.flush()
    cred = AccessCredential(employee_id=emp.id, credential_hash="cred_bob", status="ACTIVE")
    db_session.add(cred)
    db_session.commit()

    # 1 authorized badge swipe
    event, session = process_badge_swipe(db_session, gate.id, "cred_bob", "ENTRY")
    assert event.decision == "GRANTED"

    # 2 camera crossings observed (Person 101 and Person 102)
    ingest_person_crossing(db_session, gate.id, cam.id, "trk_101", "ENTRY", 0.95)
    ingest_person_crossing(db_session, gate.id, cam.id, "trk_102", "ENTRY", 0.92)

    # Finalize gate session
    final_session, incident = finalize_gate_session_logic(db_session, session.id)

    assert final_session.status == "FINALIZED"
    assert final_session.expected_authorized_entries == 1
    assert final_session.observed_crossings == 2
    assert final_session.unmatched_crossings == 1
    assert incident is not None
    assert incident.incident_type == "TAILGATING"
    assert incident.unmatched_count == 1
    assert incident.status == "NEW"
    outbox = db_session.query(IncidentVectorOutbox).filter_by(
        incident_id=incident.id, event_type="INCIDENT_CREATED"
    ).one()
    assert outbox.status == "PENDING"

    _, duplicate_incident = finalize_gate_session_logic(db_session, session.id)
    assert duplicate_incident.id == incident.id
    assert db_session.query(IncidentVectorOutbox).filter_by(
        incident_id=incident.id, event_type="INCIDENT_CREATED"
    ).count() == 1


def test_scenario_low_confidence_filtering(db_session):
    site = Site(site_name="HQ", address="Address")
    db_session.add(site)
    db_session.flush()
    zone = Zone(site_id=site.id, zone_name="Lobby", zone_type="PERIMETER")
    db_session.add(zone)
    db_session.flush()
    gate = Gate(zone_id=zone.id, gate_code="G-02", gate_name="Turnstile 2", direction="ENTRY", minimum_detection_confidence=0.65)
    db_session.add(gate)
    db_session.flush()
    cam = Camera(gate_id=gate.id, camera_code="C-02", camera_name="Cam 2")
    db_session.add(cam)
    emp = Employee(employee_code="E-2", full_name="Charlie", email="charlie@test.com", department="Ops")
    db_session.add(emp)
    db_session.flush()
    cred = AccessCredential(employee_id=emp.id, credential_hash="cred_charlie", status="ACTIVE")
    db_session.add(cred)
    db_session.commit()

    event, session = process_badge_swipe(db_session, gate.id, "cred_charlie", "ENTRY")

    # 1 valid crossing (0.91) and 1 noise/reflection crossing (0.35 < 0.65 threshold)
    ingest_person_crossing(db_session, gate.id, cam.id, "trk_valid", "ENTRY", 0.91)
    ingest_person_crossing(db_session, gate.id, cam.id, "trk_noise", "ENTRY", 0.35)

    final_session, incident = finalize_gate_session_logic(db_session, session.id)

    assert final_session.observed_crossings == 1
    assert final_session.unmatched_crossings == 0
    assert incident is None # Noise filtered out, normal entry


def test_investigation_lifecycle(db_session):
    user_officer = User(
        full_name="Officer Dave",
        email="dave@gatesentry.internal",
        password_hash=hash_password("Pass123!"),
        role="SECURITY_OFFICER"
    )
    db_session.add(user_officer)
    db_session.flush()

    site = Site(site_name="HQ", address="Addr")
    db_session.add(site)
    db_session.flush()
    zone = Zone(site_id=site.id, zone_name="Z1", zone_type="OFFICE")
    db_session.add(zone)
    db_session.flush()
    gate = Gate(zone_id=zone.id, gate_code="G3", gate_name="Gate 3")
    db_session.add(gate)
    db_session.flush()

    incident = Incident(
        gate_id=gate.id,
        incident_type="TAILGATING",
        authorized_count=1,
        observed_count=2,
        unmatched_count=1,
        average_confidence=0.92,
        risk_score=55.0,
        severity="MEDIUM",
        status="NEW",
        summary="Test incident"
    )
    db_session.add(incident)
    db_session.commit()

    # 1. Acknowledge
    inc_ack = acknowledge_incident(db_session, incident.id, user_officer.id, "Acknowledged by officer")
    assert inc_ack.status == "ACKNOWLEDGED"

    # 2. Resolve
    inc_res = resolve_incident(db_session, incident.id, user_officer.id, "Reviewed video. Follower was authorized staff with badge clipped behind.")
    assert inc_res.status == "RESOLVED"
    assert inc_res.resolution_notes is not None


def test_vector_crud_and_search(monkeypatch):
    class TestEmbeddingModel:
        def encode(self, text, normalize_embeddings):
            assert normalize_embeddings is True
            return [1.0] + [0.0] * 383

    # Keep this a storage/API unit test; real model availability is tested separately.
    monkeypatch.setattr(vector_service, "transformer_model", TestEmbeddingModel())
    monkeypatch.setattr(vector_service, "_model_loaded", True)
    monkeypatch.setattr(vector_service, "_embedding_error", None)

    inc_id = f"test_inc_{uuid.uuid4().hex[:8]}"
    summary = "Two individuals entered north lobby turnstile after one badge swipe. Tailgating observed."
    metadata = {
        "gate_name": "North Lobby Turnstile",
        "severity": "HIGH",
        "status": "NEW",
        "risk_score": 68.5
    }

    # CREATE
    ok_create = vector_service.upsert_incident_vector(inc_id, summary, metadata)
    assert ok_create is True

    # READ
    point = vector_service.get_incident_vector(inc_id)
    assert point is not None
    assert point["payload"]["summary"] == summary
    assert len(point["vector"]) == 384

    # UPDATE
    ok_update = vector_service.update_incident_payload(inc_id, {"status": "RESOLVED"})
    assert ok_update is True
    updated_point = vector_service.get_incident_vector(inc_id)
    assert updated_point["payload"]["status"] == "RESOLVED"

    # SEARCH
    results = vector_service.search_similar_incidents("people entering following one card swipe", limit=3, score_threshold=0.0)
    assert len(results) > 0

    # DELETE
    ok_delete = vector_service.delete_incident_vector(inc_id)
    assert ok_delete is True
    deleted_point = vector_service.get_incident_vector(inc_id)
    assert deleted_point is None


def test_embedding_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(vector_service, "transformer_model", None)
    monkeypatch.setattr(vector_service, "_model_loaded", True)
    monkeypatch.setattr(vector_service, "_embedding_error", "model unavailable in test")

    with pytest.raises(RuntimeError, match="model unavailable in test"):
        vector_service.generate_embedding("tailgating at a gate")


def make_outbox_event(db_session):
    site = Site(site_name=f"Outbox Site {uuid.uuid4()}", address="Test")
    db_session.add(site)
    db_session.flush()
    zone = Zone(site_id=site.id, zone_name="Lobby", zone_type="ENTRY")
    db_session.add(zone)
    db_session.flush()
    gate = Gate(zone_id=zone.id, gate_code=f"OUTBOX-{uuid.uuid4()}", gate_name="Outbox Gate")
    db_session.add(gate)
    db_session.flush()
    incident = Incident(
        gate_id=gate.id,
        incident_type="TAILGATING",
        authorized_count=1,
        observed_count=2,
        unmatched_count=1,
        average_confidence=0.9,
        risk_score=48.0,
        severity="MEDIUM",
        status="NEW",
        summary="One person followed an authorized entry.",
    )
    db_session.add(incident)
    db_session.flush()
    event = IncidentVectorOutbox(
        incident_id=incident.id,
        event_type="INCIDENT_CREATED",
        status="PENDING",
        payload={
            "summary": incident.summary,
            "metadata": {"gate_name": gate.gate_name, "severity": incident.severity},
        },
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_outbox_retries_qdrant_outage_and_completes_after_recovery(db_session):
    event = make_outbox_event(db_session)

    class UnavailableQdrant:
        def upsert_incident_vector(self, **kwargs):
            raise ConnectionError("Qdrant is offline")

    first = process_outbox_event(db_session, event.event_id, vector=UnavailableQdrant())
    assert first.status == "PENDING"
    assert first.attempt_count == 1
    assert first.last_error == "Qdrant is offline"

    event.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    class RestoredQdrant:
        def upsert_incident_vector(self, **kwargs):
            assert kwargs["incident_id"] == event.incident_id
            return True

    completed = process_outbox_event(db_session, event.event_id, vector=RestoredQdrant())
    assert completed.status == "COMPLETED"
    assert completed.processed_at is not None
    assert process_outbox_event(
        db_session, event.event_id, vector=RestoredQdrant()
    ).status == "COMPLETED"


def test_outbox_marks_unavailable_embeddings_permanent_and_allows_manual_retry(db_session):
    event = make_outbox_event(db_session)

    class ModelUnavailable:
        def upsert_incident_vector(self, **kwargs):
            raise EmbeddingUnavailableError("model unavailable")

    failed = process_outbox_event(db_session, event.event_id, vector=ModelUnavailable())
    assert failed.status == "FAILED"
    assert failed.attempt_count == 1

    queued = retry_failed_outbox_event(db_session, event.event_id)
    assert queued.status == "PENDING"
    assert queued.attempt_count == 0

    class RecoveredModel:
        def upsert_incident_vector(self, **kwargs):
            return True

    assert process_outbox_event(
        db_session, event.event_id, vector=RecoveredModel()
    ).status == "COMPLETED"


def test_outbox_stops_after_retry_limit(db_session, monkeypatch):
    event = make_outbox_event(db_session)
    monkeypatch.setattr("app.services.outbox_service.settings.OUTBOX_MAX_ATTEMPTS", 2)

    class QdrantFailure:
        def upsert_incident_vector(self, **kwargs):
            raise ConnectionError("permanent test outage")

    first = process_outbox_event(db_session, event.event_id, vector=QdrantFailure())
    assert first.status == "PENDING"
    first.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    second = process_outbox_event(db_session, event.event_id, vector=QdrantFailure())
    assert second.status == "FAILED"
    assert second.attempt_count == 2


def test_all_required_demo_scenarios(db_session):
    site = Site(site_name="Scenario HQ", address="Demo")
    db_session.add(site); db_session.flush()
    zone = Zone(site_id=site.id, zone_name="Lobby", zone_type="ENTRY", sensitivity_level=10)
    db_session.add(zone); db_session.flush()
    gate = Gate(zone_id=zone.id, gate_code="SCENARIO-GATE", gate_name="Scenario Gate", session_window_seconds=30)
    db_session.add(gate); db_session.flush()
    camera = Camera(gate_id=gate.id, camera_code="SCENARIO-CAM", camera_name="Synthetic Demo Camera")
    users = [Employee(employee_code=f"SCENARIO-E{i}", full_name=f"Employee {i}", email=f"scenario{i}@example.test", department="Demo") for i in (1,2)]
    officer = User(full_name="Demo Officer", email="scenario-officer@example.test", password_hash=hash_password("LocalOnly123!"), role="SECURITY_OFFICER")
    db_session.add_all([camera, *users, officer]); db_session.flush()
    db_session.add_all([AccessCredential(employee_id=e.id, credential_hash=f"scenario-cred-{i}", status="ACTIVE") for i,e in enumerate(users,1)])
    db_session.commit()

    a = execute_scenario_normal_entry(db_session, gate.id)
    assert (a["authorized_count"], a["observed_count"], a["unmatched_count"], a["incident_generated"]) == (1,1,0,False)
    b = execute_scenario_tailgating(db_session, gate.id)
    assert (b["authorized_count"], b["observed_count"], b["unmatched_count"], b["incident_generated"]) == (1,2,1,True)
    c = execute_scenario_unauthorized_entry(db_session, gate.id)
    assert (c["authorized_count"], c["observed_count"], c["unmatched_count"]) == (0,1,1)
    d = execute_scenario_multiple_authorized(db_session, gate.id)
    assert (d["authorized_count"], d["observed_count"], d["unmatched_count"], d["incident_generated"]) == (2,2,0,False)
    e = execute_scenario_multiple_tailgating(db_session, gate.id)
    assert (e["authorized_count"], e["observed_count"], e["unmatched_count"], e["incident_generated"]) == (2,4,2,True)
    f = execute_scenario_low_confidence(db_session, gate.id)
    assert (f["authorized_count"], f["observed_count"], f["unmatched_count"], f["incident_generated"]) == (1,1,0,False)
    g = execute_scenario_false_positive(db_session, gate.id)
    assert g["status"] == "FALSE_POSITIVE"
    assert "cardboard box" in g["resolution_notes"]
