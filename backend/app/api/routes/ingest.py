from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database.session import activate_database_role, get_db
from app.models.models import CameraObservation, User
from app.schemas.schemas import PersonCrossingIngest, CameraObservationResponse
from app.services.event_correlation import ingest_person_crossing
from app.core.config import settings

router = APIRouter(prefix="/ingest", tags=["Detection Ingestion"])

@router.post("/crossings", response_model=CameraObservationResponse, status_code=status.HTTP_201_CREATED)
def ingest_crossing(
    crossing: PersonCrossingIngest,
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Ingestion endpoint for external YOLOv8 + ByteTrack person tracking pipeline.
    Requires either valid X-API-Key header or authenticated user session.
    """
    if x_api_key and x_api_key == settings.DETECTOR_API_KEY:
        activate_database_role(db, "SECURITY_OFFICER")
    else:
        # Otherwise raise 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid X-API-Key required for external CCTV detector ingestion."
        )

    obs = ingest_person_crossing(
        db=db,
        gate_id=crossing.gate_id,
        camera_id=crossing.camera_id,
        tracker_id=crossing.tracker_id,
        direction=crossing.direction,
        confidence=crossing.confidence,
        timestamp=crossing.timestamp,
        evidence_reference=crossing.evidence_reference,
        external_event_id=crossing.external_event_id
    )

    return CameraObservationResponse(
        id=obs.id,
        gate_id=obs.gate_id,
        camera_id=obs.camera_id,
        gate_session_id=obs.gate_session_id,
        tracker_id=obs.tracker_id,
        observed_at=obs.observed_at,
        direction=obs.direction,
        confidence=obs.confidence,
        evidence_reference=obs.evidence_reference
    )
