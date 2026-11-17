import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Gate, Camera, AccessCredential, Employee, GateSession, Incident, User
from app.services.event_correlation import process_badge_swipe, ingest_person_crossing, finalize_gate_session_logic
from app.services.investigation_service import mark_incident_false_positive

def execute_scenario_normal_entry(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario A: 1 valid badge swipe, 1 observed crossing. Outcome: NORMAL ENTRY."""
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    if not gate:
        raise ValueError("Gate not found")
    
    cred = db.query(AccessCredential).filter(AccessCredential.status == "ACTIVE").first()
    if not cred:
        raise ValueError("No active credential found in database")

    # Step 1: Badge swipe
    event, session = process_badge_swipe(
        db=db,
        gate_id=gate.id,
        credential_hash=cred.credential_hash,
        direction="ENTRY"
    )

    # Step 2: Camera observation
    cam = gate.cameras[0] if gate.cameras else None
    camera_id = cam.id if cam else gate.id
    tracker_1 = f"demo_trk_{uuid.uuid4().hex[:6]}"
    
    obs1 = ingest_person_crossing(
        db=db,
        gate_id=gate.id,
        camera_id=camera_id,
        tracker_id=tracker_1,
        direction="ENTRY",
        confidence=0.94
    )

    # Step 3: Finalize session
    final_session, incident = finalize_gate_session_logic(db=db, session_id=session.id)

    return {
        "scenario": "NORMAL_ENTRY",
        "gate_name": gate.gate_name,
        "authorized_count": final_session.expected_authorized_entries,
        "observed_count": final_session.observed_crossings,
        "unmatched_count": final_session.unmatched_crossings,
        "incident_generated": incident is not None,
        "incident_id": incident.id if incident else None,
        "result": "NORMAL ENTRY - No discrepancy"
    }


def execute_scenario_tailgating(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario B: 1 valid swipe, 2 unique crossings. Outcome: TAILGATING INCIDENT."""
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    cred = db.query(AccessCredential).filter(AccessCredential.status == "ACTIVE").first()

    event, session = process_badge_swipe(
        db=db,
        gate_id=gate.id,
        credential_hash=cred.credential_hash,
        direction="ENTRY"
    )

    cam = gate.cameras[0] if gate.cameras else None
    camera_id = cam.id if cam else gate.id
    
    # 2 unique trackers
    t1 = f"trk_auth_{uuid.uuid4().hex[:6]}"
    t2 = f"trk_tailgater_{uuid.uuid4().hex[:6]}"
    
    ingest_person_crossing(db, gate.id, camera_id, t1, "ENTRY", 0.95)
    ingest_person_crossing(db, gate.id, camera_id, t2, "ENTRY", 0.91)

    final_session, incident = finalize_gate_session_logic(db, session.id)

    return {
        "scenario": "TAILGATING",
        "gate_name": gate.gate_name,
        "authorized_count": final_session.expected_authorized_entries,
        "observed_count": final_session.observed_crossings,
        "unmatched_count": final_session.unmatched_crossings,
        "incident_generated": incident is not None,
        "incident_id": incident.id if incident else None,
        "risk_score": incident.risk_score if incident else None,
        "severity": incident.severity if incident else None,
        "summary": incident.summary if incident else None,
        "result": "TAILGATING DETECTED - Incident created and vectorized"
    }


def execute_scenario_unauthorized_entry(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario C: 0 swipes, 1 crossing. Outcome: UNAUTHORIZED ENTRY."""
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    cam = gate.cameras[0] if gate.cameras else None
    camera_id = cam.id if cam else gate.id
    
    now = datetime.now(timezone.utc)
    # Gate session created by unexpected crossing or door force
    session = GateSession(
        gate_id=gate.id,
        opened_at=now,
        closes_at=now + timedelta(seconds=gate.session_window_seconds),
        expected_authorized_entries=0,
        status="OPEN"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    t1 = f"trk_unauth_{uuid.uuid4().hex[:6]}"
    ingest_person_crossing(db, gate.id, camera_id, t1, "ENTRY", 0.89)

    final_session, incident = finalize_gate_session_logic(db, session.id)

    return {
        "scenario": "UNAUTHORIZED_ENTRY",
        "gate_name": gate.gate_name,
        "authorized_count": final_session.expected_authorized_entries,
        "observed_count": final_session.observed_crossings,
        "unmatched_count": final_session.unmatched_crossings,
        "incident_generated": incident is not None,
        "incident_id": incident.id if incident else None,
        "risk_score": incident.risk_score if incident else None,
        "severity": incident.severity if incident else None,
        "summary": incident.summary if incident else None,
        "result": "UNAUTHORIZED ENTRY DETECTED"
    }


def execute_scenario_multiple_authorized(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario D: 2 valid swipes, 2 crossings. Outcome: NORMAL ENTRY."""
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    creds = db.query(AccessCredential).filter(AccessCredential.status == "ACTIVE").limit(2).all()
    if len(creds) < 2:
        creds = [creds[0], creds[0]]

    # 2 badge swipes in quick succession
    ev1, session = process_badge_swipe(db, gate.id, creds[0].credential_hash, "ENTRY")
    ev2, session = process_badge_swipe(db, gate.id, creds[1].credential_hash, "ENTRY")

    cam = gate.cameras[0] if gate.cameras else None
    camera_id = cam.id if cam else gate.id

    t1 = f"trk_p1_{uuid.uuid4().hex[:6]}"
    t2 = f"trk_p2_{uuid.uuid4().hex[:6]}"
    ingest_person_crossing(db, gate.id, camera_id, t1, "ENTRY", 0.92)
    ingest_person_crossing(db, gate.id, camera_id, t2, "ENTRY", 0.94)

    final_session, incident = finalize_gate_session_logic(db, session.id)

    return {
        "scenario": "MULTIPLE_AUTHORIZED_ENTRIES",
        "gate_name": gate.gate_name,
        "authorized_count": final_session.expected_authorized_entries,
        "observed_count": final_session.observed_crossings,
        "unmatched_count": final_session.unmatched_crossings,
        "incident_generated": incident is not None,
        "incident_id": incident.id if incident else None,
        "result": "NORMAL ENTRY - Both individuals authenticated"
    }


def execute_scenario_multiple_tailgating(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario E: 2 valid swipes and 4 unique crossings; expect 2 unmatched."""
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    if not gate:
        raise ValueError("Gate not found")
    creds = db.query(AccessCredential).filter(AccessCredential.status == "ACTIVE").limit(2).all()
    if not creds:
        raise ValueError("No active credential found in database")
    selected = creds if len(creds) > 1 else [creds[0], creds[0]]
    _, session = process_badge_swipe(db, gate.id, selected[0].credential_hash, "ENTRY")
    process_badge_swipe(db, gate.id, selected[1].credential_hash, "ENTRY")
    camera_id = gate.cameras[0].id if gate.cameras else None
    if not camera_id:
        raise ValueError("Gate requires a configured camera for crossing observations")
    for confidence in (0.96, 0.94, 0.92, 0.90):
        ingest_person_crossing(db, gate.id, camera_id, f"trk_multi_{uuid.uuid4().hex[:10]}", "ENTRY", confidence)
    final_session, incident = finalize_gate_session_logic(db, session.id)
    return {
        "scenario": "MULTIPLE_TAILGATING",
        "gate_name": gate.gate_name,
        "authorized_count": final_session.expected_authorized_entries,
        "observed_count": final_session.observed_crossings,
        "unmatched_count": final_session.unmatched_crossings,
        "incident_generated": incident is not None,
        "incident_id": incident.id if incident else None,
        "incident_type": incident.incident_type if incident else None,
        "result": "TAILGATING DETECTED - two unmatched crossings" if incident else "No incident generated",
    }


def execute_scenario_low_confidence(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario F: 1 valid swipe, 1 confirmed crossing (0.92), 1 low-confidence crossing (0.42 < 0.65 threshold)."""
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    cred = db.query(AccessCredential).filter(AccessCredential.status == "ACTIVE").first()

    event, session = process_badge_swipe(db, gate.id, cred.credential_hash, "ENTRY")
    cam = gate.cameras[0] if gate.cameras else None
    camera_id = cam.id if cam else gate.id

    t1 = f"trk_valid_{uuid.uuid4().hex[:6]}"
    t2 = f"trk_ghost_artifact_{uuid.uuid4().hex[:6]}"

    # Observation 1: high confidence crossing
    ingest_person_crossing(db, gate.id, camera_id, t1, "ENTRY", 0.93)
    # Observation 2: low confidence reflection / shadow (below 0.65 threshold)
    ingest_person_crossing(db, gate.id, camera_id, t2, "ENTRY", 0.42)

    final_session, incident = finalize_gate_session_logic(db, session.id)

    return {
        "scenario": "LOW_CONFIDENCE_OBSERVATION",
        "gate_name": gate.gate_name,
        "authorized_count": final_session.expected_authorized_entries,
        "observed_count": final_session.observed_crossings,
        "unmatched_count": final_session.unmatched_crossings,
        "incident_generated": incident is not None,
        "explanation": "Second crossing was 0.42 (below 0.65 threshold) and ignored from incident tally.",
        "result": "NORMAL ENTRY - Noise filtered by confidence engine"
    }


def execute_scenario_false_positive(db: Session, gate_id: str) -> Dict[str, Any]:
    """Scenario G: Generates tailgating incident, then marks it FALSE_POSITIVE."""
    # First trigger tailgating
    tailgating_result = execute_scenario_tailgating(db, gate_id)
    incident_id = tailgating_result.get("incident_id")
    if not incident_id:
        return {"error": "Failed to create initial incident"}

    admin_user = db.query(User).filter(User.role.in_(["ADMIN", "SECURITY_OFFICER"])).first()
    user_id = admin_user.id if admin_user else str(uuid.uuid4())

    updated_inc = mark_incident_false_positive(
        db=db,
        incident_id=incident_id,
        user_id=user_id,
        explanation="Evaluated by security officer: employee was carrying a large cardboard box causing secondary bounding box detection."
    )

    return {
        "scenario": "FALSE_POSITIVE_RESOLVED",
        "incident_id": updated_inc.id,
        "status": updated_inc.status,
        "resolution_notes": updated_inc.resolution_notes,
        "result": "INCIDENT CLASSIFIED AS FALSE POSITIVE WITH EXPLANATION"
    }
