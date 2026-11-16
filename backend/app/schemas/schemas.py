from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------
# AUTHENTICATION SCHEMAS
# ---------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    email: str

class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str = "SECURITY_OFFICER"

# ---------------------------------------------------------
# EMPLOYEE SCHEMAS
# ---------------------------------------------------------
class EmployeeBase(BaseModel):
    employee_code: str
    full_name: str
    email: EmailStr
    department: str
    is_active: bool = True

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

class EmployeeResponse(EmployeeBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# GATE & CAMERA SCHEMAS
# ---------------------------------------------------------
class GateBase(BaseModel):
    zone_id: str
    gate_code: str
    gate_name: str
    direction: str = "ENTRY"
    is_active: bool = True
    session_window_seconds: int = 8
    minimum_detection_confidence: float = 0.65

class GateCreate(GateBase):
    pass

class GateUpdate(BaseModel):
    gate_name: Optional[str] = None
    is_active: Optional[bool] = None
    session_window_seconds: Optional[int] = None
    minimum_detection_confidence: Optional[float] = None

class GateResponse(GateBase):
    id: str
    created_at: datetime
    zone_name: Optional[str] = None
    site_name: Optional[str] = None

    class Config:
        from_attributes = True

class CameraResponse(BaseModel):
    id: str
    gate_id: str
    camera_code: str
    camera_name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# ACCESS EVENT SCHEMAS
# ---------------------------------------------------------
class AccessEventCreate(BaseModel):
    gate_id: str
    credential_hash: str
    direction: str = "ENTRY"
    external_event_id: Optional[str] = None

class AccessEventResponse(BaseModel):
    id: str
    gate_id: str
    credential_id: Optional[str]
    event_timestamp: datetime
    direction: str
    decision: str
    denial_reason: Optional[str]
    external_event_id: Optional[str]
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# INGESTION & TRACKING SCHEMAS
# ---------------------------------------------------------
class PersonCrossingIngest(BaseModel):
    gate_id: str
    camera_id: str
    tracker_id: str
    direction: str = "ENTRY"
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    evidence_reference: Optional[str] = None
    external_event_id: Optional[str] = None

class CameraObservationResponse(BaseModel):
    id: str
    gate_id: str
    camera_id: str
    gate_session_id: Optional[str]
    tracker_id: str
    observed_at: datetime
    direction: str
    confidence: float
    evidence_reference: Optional[str]

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# GATE SESSIONS
# ---------------------------------------------------------
class GateSessionResponse(BaseModel):
    id: str
    gate_id: str
    gate_name: Optional[str] = None
    opened_at: datetime
    closes_at: datetime
    expected_authorized_entries: int
    observed_crossings: int
    unmatched_crossings: int
    status: str
    finalized_at: Optional[datetime]

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# INCIDENT SCHEMAS
# ---------------------------------------------------------
class IncidentActionResponse(BaseModel):
    id: str
    incident_id: str
    actor_id: str
    actor_name: Optional[str] = None
    action_type: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True

class EvidenceAssetResponse(BaseModel):
    id: str
    incident_id: str
    object_reference: str
    media_type: str
    checksum: str
    is_redacted: bool
    created_at: datetime

    class Config:
        from_attributes = True

class IncidentResponse(BaseModel):
    id: str
    gate_id: str
    gate_name: Optional[str] = None
    zone_name: Optional[str] = None
    site_name: Optional[str] = None
    incident_type: str
    authorized_count: int
    observed_count: int
    unmatched_count: int
    average_confidence: float
    risk_score: float
    severity: str
    status: str
    summary: str
    assigned_to: Optional[str] = None
    assigned_officer_name: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class IncidentDetailResponse(IncidentResponse):
    actions: List[IncidentActionResponse] = []
    evidence: List[EvidenceAssetResponse] = []
    score_breakdown: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------
# INVESTIGATION ACTION SCHEMAS
# ---------------------------------------------------------
class AcknowledgeRequest(BaseModel):
    note: Optional[str] = "Incident acknowledged for investigation."

class AssignRequest(BaseModel):
    assigned_to_user_id: str
    note: Optional[str] = "Assigned security officer."

class AddActionRequest(BaseModel):
    action_type: str = "NOTE"
    description: str

class ResolveRequest(BaseModel):
    resolution_notes: str

class FalsePositiveRequest(BaseModel):
    explanation: str

# ---------------------------------------------------------
# VECTOR SEARCH SCHEMAS
# ---------------------------------------------------------
class VectorSearchRequest(BaseModel):
    query: str
    limit: int = 5
    score_threshold: float = 0.20
    severity: Optional[str] = None
    status: Optional[str] = None

class VectorSearchResult(BaseModel):
    incident_id: str
    similarity_score: float
    gate_name: Optional[str] = None
    site_name: Optional[str] = None
    incident_type: str
    severity: str
    status: str
    risk_score: float
    created_at: Optional[str] = None
    summary: str

# ---------------------------------------------------------
# ANALYTICS SCHEMAS
# ---------------------------------------------------------
class OverviewStats(BaseModel):
    total_access_events: int
    successful_entries: int
    denied_entries: int
    total_observed_crossings: int
    tailgating_incidents: int
    unauthorized_entry_incidents: int
    critical_incidents: int
    high_incidents: int
    medium_incidents: int
    low_incidents: int
    average_risk_score: float
    average_resolution_hours: float

class TrendPoint(BaseModel):
    date: str
    incidents_count: int
    tailgating_count: int
    unauthorized_count: int

class GateStat(BaseModel):
    gate_id: str
    gate_name: str
    gate_code: str
    site_name: str
    incident_count: int
    avg_risk: float

class SeverityBreakdown(BaseModel):
    low: int
    medium: int
    high: int
    critical: int

# ---------------------------------------------------------
# AUDIT LOG SCHEMAS
# ---------------------------------------------------------
class AuditLogResponse(BaseModel):
    id: str
    actor_user_id: Optional[str]
    actor_name: Optional[str] = None
    entity_type: str
    entity_id: str
    action: str
    old_values: Optional[Any] = None
    new_values: Optional[Any] = None
    occurred_at: datetime

    class Config:
        from_attributes = True
