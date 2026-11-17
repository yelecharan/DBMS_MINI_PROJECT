from typing import Optional, Any
import json
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.session import DATABASE_URL
from app.models.models import AuditLog
import logging

logger = logging.getLogger("gatesentry.audit")

def log_audit_event(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_user_id: Optional[str] = None,
    old_values: Optional[Any] = None,
    new_values: Optional[Any] = None,
    commit: bool = True,
) -> AuditLog:
    """Create an immutable audit log entry."""
    if DATABASE_URL.startswith(("postgresql://", "postgresql+")):
        db.flush()
        connection = db.connection()
        previous_role = connection.info.get("gatesentry_database_role")
        connection.exec_driver_sql("SET LOCAL ROLE gg_audit_writer")
        audit_row = db.execute(
            text(
                "SELECT * FROM public.append_audit_log("
                "CAST(:actor_user_id AS uuid), :entity_type, :entity_id, :action, "
                "CAST(:old_values AS jsonb), CAST(:new_values AS jsonb))"
            ),
            {
                "actor_user_id": actor_user_id,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "action": action,
                "old_values": json.dumps(old_values) if old_values is not None else None,
                "new_values": json.dumps(new_values) if new_values is not None else None,
            },
        ).mappings().one()
        if commit:
            db.commit()
        elif previous_role:
            db.connection().exec_driver_sql(f"SET LOCAL ROLE {previous_role}")
        else:
            db.connection().exec_driver_sql("RESET ROLE")
        audit_entry = AuditLog(**audit_row)
        logger.info("Audit log created: [%s] %s %s by %s", action, entity_type, entity_id, actor_user_id)
        return audit_entry

    audit_entry = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_values=old_values,
        new_values=new_values
    )
    db.add(audit_entry)
    if commit:
        db.commit()
        db.refresh(audit_entry)
    logger.info(f"Audit log created: [{action}] {entity_type} {entity_id} by {actor_user_id}")
    return audit_entry
