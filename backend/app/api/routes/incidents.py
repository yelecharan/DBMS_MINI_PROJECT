from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.models import Incident, User, IncidentAction, EvidenceAsset
from app.schemas.schemas import IncidentResponse, IncidentDetailResponse, IncidentActionResponse, EvidenceAssetResponse
from app.api.dependencies.auth import get_current_user, require_role
from app.services.risk_engine import calculate_risk_score

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get("", response_model=List[IncidentResponse])
def list_incidents(
    gate_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    incident_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve security incidents with comprehensive filtering and sorting."""
    query = db.query(Incident)
    if gate_id:
        query = query.filter(Incident.gate_id == gate_id)
    if severity:
        query = query.filter(Incident.severity == severity)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    if search:
        query = query.filter(Incident.summary.ilike(f"%{search}%"))

    incidents = query.order_by(Incident.created_at.desc()).offset(offset).limit(limit).all()
    results = []
    for inc in incidents:
        results.append(IncidentResponse(
            id=inc.id,
            gate_id=inc.gate_id,
            gate_name=inc.gate.gate_name if inc.gate else None,
            zone_name=inc.gate.zone.zone_name if inc.gate and inc.gate.zone else None,
            site_name=inc.gate.zone.site.site_name if inc.gate and inc.gate.zone and inc.gate.zone.site else None,
            incident_type=inc.incident_type,
            authorized_count=inc.authorized_count,
            observed_count=inc.observed_count,
            unmatched_count=inc.unmatched_count,
            average_confidence=inc.average_confidence,
            risk_score=inc.risk_score,
            severity=inc.severity,
            status=inc.status,
            summary=inc.summary,
            assigned_to=inc.assigned_to,
            assigned_officer_name=inc.assignee.full_name if inc.assignee else None,
            resolution_notes=inc.resolution_notes,
            created_at=inc.created_at,
            updated_at=inc.updated_at
        ))
    return results

@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve incident detail with action history, evidence references, and explainable risk breakdown."""
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Calculate explainable score breakdown
    zone_bonus = 5
    if inc.gate and inc.gate.zone:
        zone_bonus = inc.gate.zone.sensitivity_level or 5
    
    score_calc = calculate_risk_score(
        unmatched_count=inc.unmatched_count,
        average_confidence=inc.average_confidence,
        zone_sensitivity_bonus=zone_bonus
    )

    action_items = []
    for a in inc.actions:
        action_items.append(IncidentActionResponse(
            id=a.id,
            incident_id=a.incident_id,
            actor_id=a.actor_id or "",
            actor_name=a.actor.full_name if a.actor else "GateSentry System",
            action_type=a.action_type,
            description=a.description,
            created_at=a.created_at
        ))

    evidence_items = []
    for e in inc.evidence:
        evidence_items.append(EvidenceAssetResponse(
            id=e.id,
            incident_id=e.incident_id,
            object_reference=e.object_reference,
            media_type=e.media_type,
            checksum=e.checksum,
            is_redacted=e.is_redacted,
            created_at=e.created_at
        ))

    return IncidentDetailResponse(
        id=inc.id,
        gate_id=inc.gate_id,
        gate_name=inc.gate.gate_name if inc.gate else None,
        zone_name=inc.gate.zone.zone_name if inc.gate and inc.gate.zone else None,
        site_name=inc.gate.zone.site.site_name if inc.gate and inc.gate.zone and inc.gate.zone.site else None,
        incident_type=inc.incident_type,
        authorized_count=inc.authorized_count,
        observed_count=inc.observed_count,
        unmatched_count=inc.unmatched_count,
        average_confidence=inc.average_confidence,
        risk_score=inc.risk_score,
        severity=inc.severity,
        status=inc.status,
        summary=inc.summary,
        assigned_to=inc.assigned_to,
        assigned_officer_name=inc.assignee.full_name if inc.assignee else None,
        resolution_notes=inc.resolution_notes,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
        actions=action_items,
        evidence=evidence_items,
        score_breakdown=score_calc.to_dict()
    )
