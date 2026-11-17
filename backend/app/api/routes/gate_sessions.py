from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.models import GateSession, User
from app.schemas.schemas import GateSessionResponse, IncidentResponse
from app.api.dependencies.auth import get_current_user, require_role
from app.services.event_correlation import finalize_gate_session_logic

router = APIRouter(prefix="/gate-sessions", tags=["Gate Sessions"])

@router.get("", response_model=List[GateSessionResponse])
def list_gate_sessions(
    gate_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(GateSession)
    if gate_id:
        query = query.filter(GateSession.gate_id == gate_id)
    if status:
        query = query.filter(GateSession.status == status)

    sessions = query.order_by(GateSession.opened_at.desc()).limit(limit).all()
    results = []
    for s in sessions:
        results.append(GateSessionResponse(
            id=s.id,
            gate_id=s.gate_id,
            gate_name=s.gate.gate_name if s.gate else None,
            opened_at=s.opened_at,
            closes_at=s.closes_at,
            expected_authorized_entries=s.expected_authorized_entries,
            observed_crossings=s.observed_crossings,
            unmatched_crossings=s.unmatched_crossings,
            status=s.status,
            finalized_at=s.finalized_at
        ))
    return results

@router.get("/{session_id}", response_model=GateSessionResponse)
def get_gate_session(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    s = db.query(GateSession).filter(GateSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Gate session not found")
    return GateSessionResponse(
        id=s.id,
        gate_id=s.gate_id,
        gate_name=s.gate.gate_name if s.gate else None,
        opened_at=s.opened_at,
        closes_at=s.closes_at,
        expected_authorized_entries=s.expected_authorized_entries,
        observed_crossings=s.observed_crossings,
        unmatched_crossings=s.unmatched_crossings,
        status=s.status,
        finalized_at=s.finalized_at
    )

@router.post("/{session_id}/finalize")
def finalize_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"])),
):
    """Close and finalize gate session, correlate access records, and generate incident if unmatched."""
    try:
        session, incident = finalize_gate_session_logic(db=db, session_id=session_id)
        return {
            "session_id": session.id,
            "status": session.status,
            "authorized_count": session.expected_authorized_entries,
            "observed_count": session.observed_crossings,
            "unmatched_count": session.unmatched_crossings,
            "incident_created": incident is not None,
            "incident_id": incident.id if incident else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
