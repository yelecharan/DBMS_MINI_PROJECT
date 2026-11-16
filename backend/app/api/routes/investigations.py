from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import User
from app.schemas.schemas import (
    IncidentResponse, AcknowledgeRequest, AssignRequest, 
    AddActionRequest, ResolveRequest, FalsePositiveRequest
)
from app.api.dependencies.auth import get_current_user, require_role
from app.services.investigation_service import (
    acknowledge_incident, assign_incident, add_investigation_action,
    resolve_incident, mark_incident_false_positive
)

router = APIRouter(prefix="/incidents", tags=["Investigations"])

@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def api_acknowledge_incident(
    incident_id: str,
    body: AcknowledgeRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Acknowledge an incident and assign it to the current security officer."""
    try:
        inc = acknowledge_incident(db, incident_id, officer.id, body.note)
        return inc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{incident_id}/assign", response_model=IncidentResponse)
def api_assign_incident(
    incident_id: str,
    body: AssignRequest,
    db: Session = Depends(get_db),
    admin_or_lead: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Assign incident to a designated security officer (Admin or Security Lead only)."""
    try:
        inc = assign_incident(db, incident_id, body.assigned_to_user_id, admin_or_lead.id, body.note)
        return inc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{incident_id}/actions")
def api_add_investigation_action(
    incident_id: str,
    body: AddActionRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Add investigation note or progress entry."""
    try:
        act = add_investigation_action(db, incident_id, officer.id, body.action_type, body.description)
        return {
            "id": act.id,
            "action_type": act.action_type,
            "description": act.description,
            "actor_name": officer.full_name,
            "created_at": act.created_at
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
def api_resolve_incident(
    incident_id: str,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Mark an incident as resolved with comprehensive investigation findings."""
    try:
        inc = resolve_incident(db, incident_id, officer.id, body.resolution_notes)
        return inc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{incident_id}/false-positive", response_model=IncidentResponse)
def api_false_positive_incident(
    incident_id: str,
    body: FalsePositiveRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Mark an incident as a false positive with justification."""
    try:
        inc = mark_incident_false_positive(db, incident_id, officer.id, body.explanation)
        return inc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
