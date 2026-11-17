from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.models import AuditLog, User
from app.schemas.schemas import AuditLogResponse
from app.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])

@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve immutable audit log records.
    Accessible to AUDITOR, SECURITY_OFFICER and ADMIN roles.
    """
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)

    logs = query.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit).all()
    results = []
    for log in logs:
        actor_name = None
        if log.actor_user_id:
            user = db.query(User).filter(User.id == log.actor_user_id).first()
            if user:
                actor_name = user.full_name
        else:
            actor_name = "System Event Correlation Engine"

        results.append(AuditLogResponse(
            id=log.id,
            actor_user_id=log.actor_user_id,
            actor_name=actor_name,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            old_values=log.old_values,
            new_values=log.new_values,
            occurred_at=log.occurred_at
        ))
    return results
