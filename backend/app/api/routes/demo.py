from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import Base, get_db
from app.core.config import settings
from app.models.models import Gate, User
from app.services.demo_service import (
    execute_scenario_normal_entry,
    execute_scenario_tailgating,
    execute_scenario_unauthorized_entry,
    execute_scenario_multiple_authorized,
    execute_scenario_multiple_tailgating,
    execute_scenario_low_confidence,
    execute_scenario_false_positive
)
from app.api.dependencies.auth import require_role

router = APIRouter(prefix="/demo", tags=["Demonstration Scenarios"])

def _get_target_gate(db: Session, gate_id: str = None) -> str:
    if gate_id:
        return gate_id
    gate = db.query(Gate).filter(Gate.is_active == True).first()
    if not gate:
        raise HTTPException(status_code=400, detail="No active gate available. Run reset/seed first.")
    return gate.id

@router.post("/scenarios/normal-entry")
def run_normal_entry(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario A: 1 badge swipe, 1 crossing -> Normal entry (No incident)."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_normal_entry(db, gid)

@router.post("/scenarios/tailgating")
def run_tailgating(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario B: 1 badge swipe, 2 unique crossings -> Tailgating incident detected."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_tailgating(db, gid)

@router.post("/scenarios/unauthorized-entry")
def run_unauthorized_entry(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario C: 0 badge swipes, 1 crossing -> Unauthorized entry detected."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_unauthorized_entry(db, gid)

@router.post("/scenarios/multiple-authorized-entries")
def run_multiple_authorized(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario D: 2 badge swipes, 2 crossings -> Normal entry."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_multiple_authorized(db, gid)

@router.post("/scenarios/multiple-tailgating")
def run_multiple_tailgating(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario E: 2 badge swipes and 4 unique crossings -> two unmatched."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_multiple_tailgating(db, gid)

@router.post("/scenarios/low-confidence")
def run_low_confidence(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario F: 1 swipe, 1 high-confidence crossing, 1 low-confidence artifact -> Noise filtered, no incident."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_low_confidence(db, gid)

@router.post("/scenarios/false-positive")
def run_false_positive(gate_id: str = None, db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN", "SECURITY_OFFICER"]))):
    """Scenario G: Generates tailgating incident then security officer marks it false positive with note."""
    gid = _get_target_gate(db, gate_id)
    return execute_scenario_false_positive(db, gid)

@router.post("/reset")
def reset_demo_database(db: Session = Depends(get_db), current_user: User = Depends(require_role(["ADMIN"]))):
    """Reset the development database and repopulate demonstration records."""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=403, detail="Demo reset is only available in development.")

    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())

    from app.seed.seed_data import seed_database
    seed_database(db)
    return {"message": "Demonstration database successfully reset and seeded."}
