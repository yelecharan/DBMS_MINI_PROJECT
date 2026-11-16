import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.database.session import DATABASE_URL
from app.models.models import Incident, IncidentVectorOutbox
from app.services.vector_service import (
    EmbeddingUnavailableError,
    vector_service,
)

logger = logging.getLogger("gatesentry.outbox")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_incident_vector_event(
    db: Session,
    incident: Incident,
    event_type: str = "INCIDENT_UPDATED",
) -> IncidentVectorOutbox:
    gate = incident.gate
    metadata = {
        "gate_name": gate.gate_name if gate else "Gate",
        "site_name": (
            gate.zone.site.site_name
            if gate and gate.zone and gate.zone.site
            else "Site"
        ),
        "incident_type": incident.incident_type,
        "severity": incident.severity,
        "status": incident.status,
        "risk_score": incident.risk_score,
        "created_at": incident.created_at.isoformat()
        if incident.created_at
        else _utcnow().isoformat(),
    }
    event = IncidentVectorOutbox(
        incident_id=incident.id,
        event_type=event_type,
        status="PENDING",
        payload={"summary": incident.summary, "metadata": metadata},
        created_at=_utcnow(),
        next_attempt_at=_utcnow(),
    )
    if DATABASE_URL.startswith(("postgresql://", "postgresql+")):
        event_row = db.execute(
            text(
                "SELECT * FROM public.enqueue_incident_vector_event("
                "CAST(:incident_id AS uuid), :event_type, CAST(:payload AS jsonb))"
            ),
            {
                "incident_id": incident.id,
                "event_type": event_type,
                "payload": json.dumps(event.payload),
            },
        ).mappings().one()
        return IncidentVectorOutbox(**event_row)

    db.add(event)
    return event


def _is_claimable(event: IncidentVectorOutbox, now: datetime) -> bool:
    if event.status == "PENDING":
        retry_at = event.next_attempt_at
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return retry_at <= now
    if event.status == "PROCESSING":
        if event.locked_at is None:
            return True
        locked_at = event.locked_at
        if locked_at.tzinfo is None:
            locked_at = locked_at.replace(tzinfo=timezone.utc)
        return locked_at <= now - timedelta(seconds=settings.OUTBOX_LOCK_TIMEOUT_SECONDS)
    return False


def process_outbox_event(
    db: Session,
    event_id: str,
    vector=vector_service,
    now: Optional[datetime] = None,
) -> IncidentVectorOutbox:
    """Claim and process one event; Qdrant upserts are idempotent by incident ID."""
    now = now or _utcnow()
    event = (
        db.query(IncidentVectorOutbox)
        .filter(IncidentVectorOutbox.event_id == event_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if event is None:
        raise ValueError(f"Outbox event {event_id} not found")
    if not _is_claimable(event, now):
        return event

    event.status = "PROCESSING"
    event.attempt_count += 1
    event.locked_at = now
    db.commit()
    db.refresh(event)

    payload = event.payload
    try:
        vector.upsert_incident_vector(
            incident_id=event.incident_id,
            text_summary=payload["summary"],
            metadata=payload["metadata"],
            raise_errors=True,
        )
    except EmbeddingUnavailableError as exc:
        event.status = "FAILED"
        event.locked_at = None
        event.last_error = str(exc)[:4000]
        db.commit()
        logger.error(
            "Outbox event %s permanently failed because embeddings are unavailable",
            event.event_id,
            exc_info=exc,
        )
    except Exception as exc:
        event.status = (
            "FAILED"
            if event.attempt_count >= settings.OUTBOX_MAX_ATTEMPTS
            else "PENDING"
        )
        delay = min(
            settings.OUTBOX_RETRY_MAX_SECONDS,
            settings.OUTBOX_RETRY_BASE_SECONDS
            * (2 ** max(0, event.attempt_count - 1)),
        )
        event.next_attempt_at = now + timedelta(seconds=delay)
        event.locked_at = None
        event.last_error = str(exc)[:4000]
        db.commit()
        logger.exception(
            "Outbox event %s failed on attempt %s (status=%s)",
            event.event_id,
            event.attempt_count,
            event.status,
        )
    else:
        event.status = "COMPLETED"
        event.processed_at = _utcnow()
        event.locked_at = None
        event.last_error = None
        db.commit()
        logger.info("Outbox event %s processed for incident %s", event.event_id, event.incident_id)

    db.refresh(event)
    return event


def process_pending_outbox(
    session_factory: sessionmaker,
    vector=vector_service,
    limit: Optional[int] = None,
) -> int:
    """Process due and expired-lease events, recovering work after a restart."""
    now = _utcnow()
    lease_cutoff = now - timedelta(seconds=settings.OUTBOX_LOCK_TIMEOUT_SECONDS)
    with session_factory() as db:
        event_ids = [
            row.event_id
            for row in (
                db.query(IncidentVectorOutbox)
                .filter(
                    or_(
                        (
                            (IncidentVectorOutbox.status == "PENDING")
                            & (IncidentVectorOutbox.next_attempt_at <= now)
                        ),
                        (
                            (IncidentVectorOutbox.status == "PROCESSING")
                            & (
                                IncidentVectorOutbox.locked_at.is_(None)
                                | (IncidentVectorOutbox.locked_at <= lease_cutoff)
                            )
                        ),
                    )
                )
                .order_by(IncidentVectorOutbox.created_at)
                .limit(limit or settings.OUTBOX_BATCH_SIZE)
                .all()
            )
        ]

    processed = 0
    for event_id in event_ids:
        with session_factory() as db:
            event = process_outbox_event(db, event_id, vector=vector)
            if event.status in ("COMPLETED", "FAILED"):
                processed += 1
    return processed


def retry_failed_outbox_event(db: Session, event_id: str) -> IncidentVectorOutbox:
    event = (
        db.query(IncidentVectorOutbox)
        .filter(IncidentVectorOutbox.event_id == event_id)
        .with_for_update()
        .first()
    )
    if event is None:
        raise ValueError(f"Outbox event {event_id} not found")
    if event.status != "FAILED":
        raise ValueError(f"Outbox event {event_id} is not in FAILED status")

    event.status = "PENDING"
    event.attempt_count = 0
    event.next_attempt_at = _utcnow()
    event.locked_at = None
    db.commit()
    db.refresh(event)
    logger.info("Manually retried outbox event %s", event.event_id)
    return event
