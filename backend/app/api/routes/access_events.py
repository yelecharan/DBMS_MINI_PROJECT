from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.models import AccessEvent, AccessCredential, Employee, User
from app.schemas.schemas import AccessEventCreate, AccessEventResponse
from app.api.dependencies.auth import get_current_user, require_role
from app.services.event_correlation import process_badge_swipe

router = APIRouter(prefix="/access-events", tags=["Access Events"])

@router.get("", response_model=List[AccessEventResponse])
def list_access_events(
    gate_id: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve logged badge swipes with decision and employee details."""
    query = db.query(AccessEvent)
    if gate_id:
        query = query.filter(AccessEvent.gate_id == gate_id)
    if decision:
        query = query.filter(AccessEvent.decision == decision)

    events = query.order_by(AccessEvent.event_timestamp.desc()).limit(limit).all()
    results = []
    for ev in events:
        emp_name = None
        emp_code = None
        if ev.credential and ev.credential.employee:
            emp_name = ev.credential.employee.full_name
            emp_code = ev.credential.employee.employee_code

        results.append(AccessEventResponse(
            id=ev.id,
            gate_id=ev.gate_id,
            credential_id=ev.credential_id,
            event_timestamp=ev.event_timestamp,
            direction=ev.direction,
            decision=ev.decision,
            denial_reason=ev.denial_reason,
            external_event_id=ev.external_event_id,
            employee_name=emp_name,
            employee_code=emp_code
        ))
    return results

@router.post("", response_model=AccessEventResponse)
def record_badge_swipe(
    swipe_in: AccessEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Simulate or record an employee badge swipe at an access control reader."""
    try:
        event, session = process_badge_swipe(
            db=db,
            gate_id=swipe_in.gate_id,
            credential_hash=swipe_in.credential_hash,
            direction=swipe_in.direction,
            external_event_id=swipe_in.external_event_id
        )
        emp_name = None
        emp_code = None
        if event.credential and event.credential.employee:
            emp_name = event.credential.employee.full_name
            emp_code = event.credential.employee.employee_code

        return AccessEventResponse(
            id=event.id,
            gate_id=event.gate_id,
            credential_id=event.credential_id,
            event_timestamp=event.event_timestamp,
            direction=event.direction,
            decision=event.decision,
            denial_reason=event.denial_reason,
            external_event_id=event.external_event_id,
            employee_name=emp_name,
            employee_code=emp_code
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
