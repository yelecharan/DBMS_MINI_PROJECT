from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.models.models import (
    Gate, GateSession, AccessEvent, AccessCredential, Employee, 
    CameraObservation, Incident, IncidentAction, AuditLog
)
from app.services.risk_engine import calculate_risk_score
from app.services.audit_service import log_audit_event
from app.services.outbox_service import enqueue_incident_vector_event
import logging

logger = logging.getLogger("gatesentry.correlation")

def to_utc_dt(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def process_badge_swipe(
    db: Session,
    gate_id: str,
    credential_hash: str,
    direction: str = "ENTRY",
    external_event_id: Optional[str] = None
) -> Tuple[AccessEvent, Optional[GateSession]]:
    """
    Evaluate badge swipe against access credentials and correlate with gate session.
    """
    now = datetime.now(timezone.utc)
    gate = db.query(Gate).filter(Gate.id == gate_id).first()
    if not gate:
        raise ValueError(f"Gate {gate_id} not found")

    # Idempotency check
    if external_event_id:
        existing = db.query(AccessEvent).filter(AccessEvent.external_event_id == external_event_id).first()
        if existing:
            return existing, None

    # Check credential
    cred = db.query(AccessCredential).filter(AccessCredential.credential_hash == credential_hash).first()
    decision = "DENIED"
    denial_reason = None
    credential_id = None

    if not cred:
        denial_reason = "Unrecognized credential identifier"
    elif cred.status != "ACTIVE":
        denial_reason = f"Credential status is {cred.status}"
        credential_id = cred.id
    else:
        v_from = to_utc_dt(cred.valid_from)
        v_until = to_utc_dt(cred.valid_until)
        if v_from and v_from > now:
            denial_reason = "Credential not yet valid"
            credential_id = cred.id
        elif v_until and v_until < now:
            denial_reason = "Credential expired"
            credential_id = cred.id
        else:
            # Check employee status
            emp = db.query(Employee).filter(Employee.id == cred.employee_id).first()
            if not emp or not emp.is_active:
                denial_reason = "Employee account inactive or deactivated"
                credential_id = cred.id
            elif gate.direction != "BIDIRECTIONAL" and gate.direction != direction:
                denial_reason = f"Gate does not permit {direction} movement"
                credential_id = cred.id
            else:
                decision = "GRANTED"
                credential_id = cred.id

    access_event = AccessEvent(
        gate_id=gate_id,
        credential_id=credential_id,
        event_timestamp=now,
        direction=direction,
        decision=decision,
        denial_reason=denial_reason,
        external_event_id=external_event_id
    )
    db.add(access_event)
    db.flush()

    active_session = None
    if decision == "GRANTED" and direction == "ENTRY":
        # Find active session
        active_session = db.query(GateSession).filter(
            GateSession.gate_id == gate_id,
            GateSession.status == "OPEN",
            GateSession.closes_at >= now
        ).first()

        if active_session:
            active_session.expected_authorized_entries += 1
            # Extend closing window
            active_session.closes_at = now + timedelta(seconds=gate.session_window_seconds)
        else:
            active_session = GateSession(
                gate_id=gate_id,
                opened_at=now,
                closes_at=now + timedelta(seconds=gate.session_window_seconds),
                expected_authorized_entries=1,
                observed_crossings=0,
                unmatched_crossings=0,
                status="OPEN"
            )
            db.add(active_session)

    db.commit()
    db.refresh(access_event)
    if active_session:
        db.refresh(active_session)
    return access_event, active_session


def ingest_person_crossing(
    db: Session,
    gate_id: str,
    camera_id: str,
    tracker_id: str,
    direction: str = "ENTRY",
    confidence: float = 0.85,
    timestamp: Optional[datetime] = None,
    evidence_reference: Optional[str] = None,
    external_event_id: Optional[str] = None
) -> CameraObservation:
    """
    Ingest person crossing observation from camera/ByteTrack.
    """
    now = timestamp or datetime.now(timezone.utc)
    if external_event_id:
        existing = db.query(CameraObservation).filter(CameraObservation.external_event_id == external_event_id).first()
        if existing:
            return existing

    # Find active gate session
    session = db.query(GateSession).filter(
        GateSession.gate_id == gate_id,
        GateSession.status == "OPEN",
        GateSession.opened_at <= now,
        GateSession.closes_at >= now - timedelta(seconds=2) # 2s grace
    ).first()

    obs = CameraObservation(
        gate_id=gate_id,
        camera_id=camera_id,
        gate_session_id=session.id if session else None,
        tracker_id=str(tracker_id),
        observed_at=now,
        direction=direction,
        confidence=float(confidence),
        evidence_reference=evidence_reference,
        external_event_id=external_event_id
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return obs


def finalize_gate_session_logic(
    db: Session,
    session_id: str
) -> Tuple[GateSession, Optional[Incident]]:
    """
    Evaluate gate session, tally authorized and observed entries, and create incident if discrepancy occurs.
    """
    session = db.query(GateSession).filter(GateSession.id == session_id).first()
    if not session:
        raise ValueError(f"Gate session {session_id} not found")

    existing_incident = db.query(Incident).filter(Incident.gate_session_id == session_id).first()
    if existing_incident:
        return session, existing_incident

    if session.status != "OPEN":
        return session, None

    gate = db.query(Gate).filter(Gate.id == session.gate_id).first()
    now = datetime.now(timezone.utc)

    # 1. Count authorized entry swipes in session window
    auth_count = db.query(func.count(AccessEvent.id)).filter(
        AccessEvent.gate_id == session.gate_id,
        AccessEvent.decision == "GRANTED",
        AccessEvent.direction == "ENTRY",
        AccessEvent.event_timestamp >= session.opened_at,
        AccessEvent.event_timestamp <= session.closes_at
    ).scalar() or 0

    # 2. Count distinct person crossings meeting confidence threshold
    obs_query = db.query(
        func.count(distinct(CameraObservation.tracker_id)),
        func.coalesce(func.avg(CameraObservation.confidence), 0.0)
    ).filter(
        CameraObservation.gate_id == session.gate_id,
        CameraObservation.direction == "ENTRY",
        CameraObservation.confidence >= gate.minimum_detection_confidence,
        CameraObservation.observed_at >= session.opened_at,
        CameraObservation.observed_at <= session.closes_at
    ).first()

    obs_count = obs_query[0] if obs_query else 0
    avg_conf = float(obs_query[1]) if obs_query else 0.0

    unmatched_count = max(0, obs_count - auth_count)

    session.expected_authorized_entries = auth_count
    session.observed_crossings = obs_count
    session.unmatched_crossings = unmatched_count
    session.status = "FINALIZED"
    session.finalized_at = now

    incident = None
    if unmatched_count > 0:
        # Check zone sensitivity bonus
        zone_bonus = 5
        if gate and gate.zone:
            zone_bonus = gate.zone.sensitivity_level or 5

        # Check repeat incidents at this gate in the last 24h
        day_ago = now - timedelta(hours=24)
        repeat_count = db.query(func.count(Incident.id)).filter(
            Incident.gate_id == gate.id,
            Incident.created_at >= day_ago
        ).scalar() or 0

        risk_calc = calculate_risk_score(
            unmatched_count=unmatched_count,
            average_confidence=avg_conf,
            zone_sensitivity_bonus=zone_bonus,
            repeat_incident_count=repeat_count
        )

        if auth_count == 0:
            incident_type = "UNAUTHORIZED_ENTRY"
            summary = (
                f"Unauthorized entry detected at {gate.gate_name}. "
                f"{obs_count} individual(s) crossed without any corresponding badge authorization. "
                f"Detection confidence was {avg_conf:.2f}."
            )
        else:
            incident_type = "TAILGATING"
            summary = (
                f"Tailgating incident detected at {gate.gate_name}. "
                f"{obs_count} individuals observed entering following {auth_count} successful employee badge authorization(s). "
                f"{unmatched_count} crossing(s) were unmatched. Detection confidence was {avg_conf:.2f}."
            )

        incident = Incident(
            gate_id=gate.id,
            gate_session_id=session.id,
            incident_type=incident_type,
            authorized_count=auth_count,
            observed_count=obs_count,
            unmatched_count=unmatched_count,
            average_confidence=round(avg_conf, 3),
            risk_score=risk_calc.final_score,
            severity=risk_calc.severity,
            status="NEW",
            summary=summary,
            created_at=now,
            updated_at=now
        )
        db.add(incident)
        db.flush()

        # Initial action
        action = IncidentAction(
            incident_id=incident.id,
            actor_id=None, # System actor
            action_type="STATUS_CHANGE",
            description="System generated incident following session correlation discrepancy.",
            created_at=now
        )
        db.add(action)

        # Audit log
        log_audit_event(
            db=db,
            entity_type="INCIDENT",
            entity_id=incident.id,
            action="CREATE",
            actor_user_id=None,
            new_values={
                "incident_type": incident.incident_type,
                "severity": incident.severity,
                "risk_score": incident.risk_score,
                "gate_id": incident.gate_id,
                "unmatched_count": incident.unmatched_count
            },
            commit=False,
        )

        enqueue_incident_vector_event(db, incident, event_type="INCIDENT_CREATED")

    db.commit()
    db.refresh(session)
    if incident:
        db.refresh(incident)
    return session, incident
