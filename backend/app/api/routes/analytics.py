from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from app.database.session import get_db
from app.models.models import (
    AccessEvent, CameraObservation, Incident, Gate, Zone, Site, 
    GateSession, User
)
from app.schemas.schemas import OverviewStats, TrendPoint, GateStat, SeverityBreakdown
from app.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics & Reporting"])

@router.get("/overview", response_model=OverviewStats)
def get_overview_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Calculate system-wide security KPIs directly from relational tables."""
    total_access = db.query(func.count(AccessEvent.id)).scalar() or 0
    granted_access = db.query(func.count(AccessEvent.id)).filter(AccessEvent.decision == "GRANTED").scalar() or 0
    denied_access = db.query(func.count(AccessEvent.id)).filter(AccessEvent.decision == "DENIED").scalar() or 0
    total_crossings = db.query(func.count(distinct(CameraObservation.tracker_id))).scalar() or 0

    tailgating_cnt = db.query(func.count(Incident.id)).filter(Incident.incident_type == "TAILGATING").scalar() or 0
    unauth_cnt = db.query(func.count(Incident.id)).filter(Incident.incident_type == "UNAUTHORIZED_ENTRY").scalar() or 0

    crit_cnt = db.query(func.count(Incident.id)).filter(Incident.severity == "CRITICAL").scalar() or 0
    high_cnt = db.query(func.count(Incident.id)).filter(Incident.severity == "HIGH").scalar() or 0
    med_cnt = db.query(func.count(Incident.id)).filter(Incident.severity == "MEDIUM").scalar() or 0
    low_cnt = db.query(func.count(Incident.id)).filter(Incident.severity == "LOW").scalar() or 0

    avg_risk = db.query(func.avg(Incident.risk_score)).scalar() or 0.0

    # Calculate average resolution time (hours)
    resolved_incidents = db.query(Incident).filter(Incident.status.in_(["RESOLVED", "FALSE_POSITIVE"])).all()
    avg_resolution_hours = 0.0
    if resolved_incidents:
        durations = [(inc.updated_at - inc.created_at).total_seconds() / 3600.0 for inc in resolved_incidents if inc.updated_at >= inc.created_at]
        if durations:
            avg_resolution_hours = sum(durations) / len(durations)

    return OverviewStats(
        total_access_events=total_access,
        successful_entries=granted_access,
        denied_entries=denied_access,
        total_observed_crossings=total_crossings,
        tailgating_incidents=tailgating_cnt,
        unauthorized_entry_incidents=unauth_cnt,
        critical_incidents=crit_cnt,
        high_incidents=high_cnt,
        medium_incidents=med_cnt,
        low_incidents=low_cnt,
        average_risk_score=round(float(avg_risk), 1),
        average_resolution_hours=round(avg_resolution_hours, 1)
    )

@router.get("/trends", response_model=List[TrendPoint])
def get_incident_trends(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve 7-day incident distribution trend."""
    results = []
    today = datetime.now(timezone.utc).date()
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        start_ts = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        end_ts = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)

        total_cnt = db.query(func.count(Incident.id)).filter(
            Incident.created_at >= start_ts, Incident.created_at <= end_ts
        ).scalar() or 0

        tg_cnt = db.query(func.count(Incident.id)).filter(
            Incident.created_at >= start_ts, Incident.created_at <= end_ts,
            Incident.incident_type == "TAILGATING"
        ).scalar() or 0

        unauth_cnt = db.query(func.count(Incident.id)).filter(
            Incident.created_at >= start_ts, Incident.created_at <= end_ts,
            Incident.incident_type == "UNAUTHORIZED_ENTRY"
        ).scalar() or 0

        results.append(TrendPoint(
            date=target_date.strftime("%b %d"),
            incidents_count=total_cnt,
            tailgating_count=tg_cnt,
            unauthorized_count=unauth_cnt
        ))
    return results

@router.get("/gates", response_model=List[GateStat])
def get_gate_incident_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Rank entrances by incident frequency and risk."""
    gates = db.query(Gate).all()
    stats = []
    for g in gates:
        cnt = db.query(func.count(Incident.id)).filter(Incident.gate_id == g.id).scalar() or 0
        avg_r = db.query(func.avg(Incident.risk_score)).filter(Incident.gate_id == g.id).scalar() or 0.0
        stats.append(GateStat(
            gate_id=g.id,
            gate_name=g.gate_name,
            gate_code=g.gate_code,
            site_name=g.zone.site.site_name if g.zone and g.zone.site else "Main",
            incident_count=cnt,
            avg_risk=round(float(avg_r), 1)
        ))
    stats.sort(key=lambda x: x.incident_count, reverse=True)
    return stats

@router.get("/severity", response_model=SeverityBreakdown)
def get_severity_breakdown(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    crit = db.query(func.count(Incident.id)).filter(Incident.severity == "CRITICAL").scalar() or 0
    high = db.query(func.count(Incident.id)).filter(Incident.severity == "HIGH").scalar() or 0
    med = db.query(func.count(Incident.id)).filter(Incident.severity == "MEDIUM").scalar() or 0
    low = db.query(func.count(Incident.id)).filter(Incident.severity == "LOW").scalar() or 0
    return SeverityBreakdown(low=low, medium=med, high=high, critical=crit)

@router.get("/live-gates")
def get_live_gate_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Real-time monitoring telemetry for each gate."""
    gates = db.query(Gate).all()
    results = []
    now = datetime.now(timezone.utc)
    for g in gates:
        # Check active session
        session = db.query(GateSession).filter(
            GateSession.gate_id == g.id,
            GateSession.status == "OPEN",
            GateSession.closes_at >= now
        ).first()

        last_access = db.query(AccessEvent).filter(
            AccessEvent.gate_id == g.id
        ).order_by(AccessEvent.event_timestamp.desc()).first()

        last_incident = db.query(Incident).filter(
            Incident.gate_id == g.id
        ).order_by(Incident.created_at.desc()).first()

        results.append({
            "gate_id": g.id,
            "gate_code": g.gate_code,
            "gate_name": g.gate_name,
            "direction": g.direction,
            "is_active": g.is_active,
            "zone_name": g.zone.zone_name if g.zone else None,
            "site_name": g.zone.site.site_name if g.zone and g.zone.site else None,
            "camera_count": len(g.cameras),
            "camera_status": g.cameras[0].status if g.cameras else "UNKNOWN",
            "session_active": session is not None,
            "session_id": session.id if session else None,
            "authorized_count": session.expected_authorized_entries if session else 0,
            "observed_count": session.observed_crossings if session else 0,
            "last_access_time": last_access.event_timestamp.isoformat() if last_access else None,
            "last_access_decision": last_access.decision if last_access else None,
            "last_incident_severity": last_incident.severity if last_incident else None,
            "last_incident_time": last_incident.created_at.isoformat() if last_incident else None,
            "last_incident_summary": last_incident.summary if last_incident else None
        })
    return results
