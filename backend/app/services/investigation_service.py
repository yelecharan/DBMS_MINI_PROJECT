from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.models import Incident, IncidentAction, User
from app.services.outbox_service import enqueue_incident_vector_event
from app.services.audit_service import log_audit_event
import logging

logger = logging.getLogger("gatesentry.investigation")

def acknowledge_incident(
    db: Session,
    incident_id: str,
    user_id: str,
    note: str = "Incident acknowledged by security officer."
) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError("Incident not found")

    old_status = incident.status
    incident.status = "ACKNOWLEDGED"
    incident.updated_at = datetime.now(timezone.utc)
    if not incident.assigned_to:
        incident.assigned_to = user_id

    action = IncidentAction(
        incident_id=incident.id,
        actor_id=user_id,
        action_type="ACKNOWLEDGE",
        description=note
    )
    db.add(action)

    log_audit_event(
        db=db,
        entity_type="INCIDENT",
        entity_id=incident.id,
        action="ACKNOWLEDGE",
        actor_user_id=user_id,
        old_values={"status": old_status},
        new_values={"status": "ACKNOWLEDGED", "assigned_to": incident.assigned_to},
        commit=False,
    )

    enqueue_incident_vector_event(db, incident)
    db.commit()
    db.refresh(incident)
    return incident


def assign_incident(
    db: Session,
    incident_id: str,
    assigned_to_user_id: str,
    current_user_id: str,
    note: str = "Assigned investigator."
) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError("Incident not found")

    target_user = db.query(User).filter(User.id == assigned_to_user_id).first()
    if not target_user:
        raise ValueError("Target user not found")

    old_assignee = incident.assigned_to
    incident.assigned_to = assigned_to_user_id
    if incident.status == "NEW":
        incident.status = "UNDER_INVESTIGATION"
    incident.updated_at = datetime.now(timezone.utc)

    action = IncidentAction(
        incident_id=incident.id,
        actor_id=current_user_id,
        action_type="ASSIGN",
        description=f"Assigned to {target_user.full_name} ({target_user.role}). Note: {note}"
    )
    db.add(action)

    log_audit_event(
        db=db,
        entity_type="INCIDENT",
        entity_id=incident.id,
        action="ASSIGN",
        actor_user_id=current_user_id,
        old_values={"assigned_to": old_assignee},
        new_values={"assigned_to": assigned_to_user_id, "status": incident.status},
        commit=False,
    )

    enqueue_incident_vector_event(db, incident)
    db.commit()
    db.refresh(incident)
    return incident


def add_investigation_action(
    db: Session,
    incident_id: str,
    user_id: str,
    action_type: str,
    description: str
) -> IncidentAction:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError("Incident not found")

    action = IncidentAction(
        incident_id=incident.id,
        actor_id=user_id,
        action_type=action_type,
        description=description
    )
    db.add(action)
    incident.updated_at = datetime.now(timezone.utc)

    log_audit_event(
        db=db,
        entity_type="INCIDENT",
        entity_id=incident.id,
        action="ADD_ACTION",
        actor_user_id=user_id,
        new_values={"action_type": action_type, "description": description},
        commit=False,
    )

    db.commit()
    db.refresh(action)
    return action


def resolve_incident(
    db: Session,
    incident_id: str,
    user_id: str,
    resolution_notes: str
) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError("Incident not found")

    old_status = incident.status
    incident.status = "RESOLVED"
    incident.resolution_notes = resolution_notes
    incident.updated_at = datetime.now(timezone.utc)

    action = IncidentAction(
        incident_id=incident.id,
        actor_id=user_id,
        action_type="RESOLVE",
        description=f"Incident resolved: {resolution_notes}"
    )
    db.add(action)

    log_audit_event(
        db=db,
        entity_type="INCIDENT",
        entity_id=incident.id,
        action="RESOLVE",
        actor_user_id=user_id,
        old_values={"status": old_status},
        new_values={"status": "RESOLVED", "resolution_notes": resolution_notes},
        commit=False,
    )

    enqueue_incident_vector_event(db, incident)

    db.commit()
    db.refresh(incident)
    return incident


def mark_incident_false_positive(
    db: Session,
    incident_id: str,
    user_id: str,
    explanation: str
) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError("Incident not found")

    old_status = incident.status
    incident.status = "FALSE_POSITIVE"
    incident.resolution_notes = f"Marked as False Positive: {explanation}"
    incident.updated_at = datetime.now(timezone.utc)

    action = IncidentAction(
        incident_id=incident.id,
        actor_id=user_id,
        action_type="FALSE_POSITIVE",
        description=f"Classified as False Positive: {explanation}"
    )
    db.add(action)

    log_audit_event(
        db=db,
        entity_type="INCIDENT",
        entity_id=incident.id,
        action="FALSE_POSITIVE",
        actor_user_id=user_id,
        old_values={"status": old_status},
        new_values={"status": "FALSE_POSITIVE", "explanation": explanation},
        commit=False,
    )

    enqueue_incident_vector_event(db, incident)

    db.commit()
    db.refresh(incident)
    return incident
