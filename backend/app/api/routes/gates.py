from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.models import Gate, Zone, Site, Camera, User
from app.schemas.schemas import GateCreate, GateUpdate, GateResponse, CameraResponse
from app.api.dependencies.auth import get_current_user, require_role
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/gates", tags=["Gates"])

@router.get("", response_model=List[GateResponse])
def list_gates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all physical gates with zone and site metadata."""
    gates = db.query(Gate).all()
    results = []
    for g in gates:
        item = GateResponse(
            id=g.id,
            zone_id=g.zone_id,
            gate_code=g.gate_code,
            gate_name=g.gate_name,
            direction=g.direction,
            is_active=g.is_active,
            session_window_seconds=g.session_window_seconds,
            minimum_detection_confidence=g.minimum_detection_confidence,
            created_at=g.created_at,
            zone_name=g.zone.zone_name if g.zone else None,
            site_name=g.zone.site.site_name if g.zone and g.zone.site else None
        )
        results.append(item)
    return results

@router.post("", response_model=GateResponse, status_code=status.HTTP_201_CREATED)
def create_gate(
    gate_in: GateCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    existing = db.query(Gate).filter(Gate.gate_code == gate_in.gate_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Gate code already registered.")

    gate = Gate(**gate_in.dict())
    db.add(gate)
    db.commit()
    db.refresh(gate)

    log_audit_event(
        db=db,
        entity_type="GATE",
        entity_id=gate.id,
        action="CREATE",
        actor_user_id=admin.id,
        new_values=gate_in.dict()
    )
    return GateResponse(
        id=gate.id,
        zone_id=gate.zone_id,
        gate_code=gate.gate_code,
        gate_name=gate.gate_name,
        direction=gate.direction,
        is_active=gate.is_active,
        session_window_seconds=gate.session_window_seconds,
        minimum_detection_confidence=gate.minimum_detection_confidence,
        created_at=gate.created_at,
        zone_name=gate.zone.zone_name if gate.zone else None,
        site_name=gate.zone.site.site_name if gate.zone and gate.zone.site else None
    )

@router.get("/{gate_id}", response_model=GateResponse)
def get_gate(gate_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    g = db.query(Gate).filter(Gate.id == gate_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Gate not found")
    return GateResponse(
        id=g.id,
        zone_id=g.zone_id,
        gate_code=g.gate_code,
        gate_name=g.gate_name,
        direction=g.direction,
        is_active=g.is_active,
        session_window_seconds=g.session_window_seconds,
        minimum_detection_confidence=g.minimum_detection_confidence,
        created_at=g.created_at,
        zone_name=g.zone.zone_name if g.zone else None,
        site_name=g.zone.site.site_name if g.zone and g.zone.site else None
    )

@router.put("/{gate_id}", response_model=GateResponse)
def update_gate(
    gate_id: str,
    update_in: GateUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    g = db.query(Gate).filter(Gate.id == gate_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Gate not found")

    old_vals = {
        "gate_name": g.gate_name,
        "is_active": g.is_active,
        "session_window_seconds": g.session_window_seconds,
        "minimum_detection_confidence": g.minimum_detection_confidence
    }
    update_data = update_in.dict(exclude_unset=True)
    for field, val in update_data.items():
        setattr(g, field, val)

    db.commit()
    db.refresh(g)

    log_audit_event(
        db=db,
        entity_type="GATE",
        entity_id=g.id,
        action="UPDATE",
        actor_user_id=admin.id,
        old_values=old_vals,
        new_values=update_data
    )
    return GateResponse(
        id=g.id,
        zone_id=g.zone_id,
        gate_code=g.gate_code,
        gate_name=g.gate_name,
        direction=g.direction,
        is_active=g.is_active,
        session_window_seconds=g.session_window_seconds,
        minimum_detection_confidence=g.minimum_detection_confidence,
        created_at=g.created_at,
        zone_name=g.zone.zone_name if g.zone else None,
        site_name=g.zone.site.site_name if g.zone and g.zone.site else None
    )

@router.get("/{gate_id}/cameras", response_model=List[CameraResponse])
def get_gate_cameras(gate_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Camera).filter(Camera.gate_id == gate_id).all()
