from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database.session import get_db
from app.models.models import Incident, IncidentVectorOutbox, User
from app.schemas.schemas import VectorSearchRequest, VectorSearchResult
from app.services.vector_service import vector_service
from app.services.outbox_service import (
    enqueue_incident_vector_event,
    retry_failed_outbox_event,
)
from app.api.dependencies.auth import get_current_user, require_role

router = APIRouter(prefix="/vector", tags=["Vector Intelligence (Qdrant)"])

@router.post("/search", response_model=List[VectorSearchResult])
def search_similar_incidents(
    req: VectorSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Search past security incidents using natural-language semantic similarity in Qdrant.
    Embeds query using all-MiniLM-L6-v2 (384-d) and calculates cosine distance.
    """
    if not vector_service.is_embedding_available():
        raise HTTPException(
            status_code=503,
            detail=vector_service.embedding_error or "Semantic embeddings are temporarily unavailable."
        )

    try:
        results = vector_service.search_similar_incidents(
            query_text=req.query,
            limit=req.limit,
            score_threshold=req.score_threshold,
            severity=req.severity,
            status=req.status,
            raise_errors=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Semantic search is temporarily unavailable: {exc}",
        ) from exc
    return results

@router.get("/incidents/{incident_id}")
def get_incident_vector_point(
    incident_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieve raw vector point and metadata payload stored in Qdrant."""
    point = vector_service.get_incident_vector(incident_id)
    if not point:
        raise HTTPException(status_code=404, detail="Vector point not found in Qdrant collection")
    return {
        "incident_id": incident_id,
        "collection": vector_service.collection_name,
        "vector_dimension": len(point["vector"]) if point["vector"] else 384,
        "payload": point["payload"],
        "sample_vector": point["vector"][:5] if point["vector"] else [] # First 5 dimensions for inspection
    }

@router.put("/incidents/{incident_id}")
def update_vector_metadata(
    incident_id: str,
    metadata: Dict[str, Any],
    officer: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))
):
    """Update incident metadata payload in Qdrant."""
    success = vector_service.update_incident_payload(incident_id, metadata)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update Qdrant payload")
    return {"message": f"Updated metadata for incident {incident_id} in Qdrant."}

@router.delete("/incidents/{incident_id}")
def delete_vector_point(
    incident_id: str,
    admin: User = Depends(require_role(["ADMIN"]))
):
    """Delete vector point from Qdrant by incident ID (Admin only)."""
    success = vector_service.delete_incident_vector(incident_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete vector from Qdrant")
    return {"message": f"Deleted vector for incident {incident_id}."}

@router.post("/sync")
def sync_all_incidents_to_qdrant(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    """Queue all relational incidents for idempotent Qdrant synchronization."""
    incidents = db.query(Incident).all()
    for inc in incidents:
        enqueue_incident_vector_event(db, inc, event_type="INCIDENT_UPDATED")
    db.commit()

    return {
        "message": f"Queued {len(incidents)} incidents for Qdrant synchronization.",
        "queued": len(incidents),
    }


@router.get("/outbox")
def list_vector_outbox_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"])),
):
    events = (
        db.query(IncidentVectorOutbox)
        .order_by(IncidentVectorOutbox.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "event_id": event.event_id,
            "incident_id": event.incident_id,
            "event_type": event.event_type,
            "status": event.status,
            "attempt_count": event.attempt_count,
            "created_at": event.created_at,
            "processed_at": event.processed_at,
            "next_attempt_at": event.next_attempt_at,
            "last_error": event.last_error,
        }
        for event in events
    ]


@router.post("/outbox/{event_id}/retry")
def retry_vector_outbox_event(
    event_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"])),
):
    try:
        event = retry_failed_outbox_event(db, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "event_id": event.event_id,
        "incident_id": event.incident_id,
        "status": event.status,
        "message": "Event queued for retry.",
    }
