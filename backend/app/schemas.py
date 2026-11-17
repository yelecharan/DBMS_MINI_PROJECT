"""Request validation models (Pydantic)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Phone = Field(pattern=r"^\+?[0-9]{10,13}$")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=63)
    password: str = Field(min_length=1, max_length=128)


# ---------------- PostgreSQL entities ----------------
class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=50)
    phone: str = Phone
    card_no: str = Field(min_length=3, max_length=20)     # first card (total participation)
    expiry_date: date


class EmployeeUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=50)
    phone: str = Phone


CardStatus = Literal["ACTIVE", "INACTIVE", "EXPIRED", "LOST"]


class CardIn(BaseModel):
    emp_id: int = Field(gt=0)
    card_no: str = Field(min_length=3, max_length=20)
    issue_date: Optional[date] = None
    expiry_date: date
    status: CardStatus = "ACTIVE"

    @model_validator(mode="after")
    def dates_ok(self):
        if self.issue_date and self.expiry_date <= self.issue_date:
            raise ValueError("expiry_date must be after issue_date")
        return self


class GateIn(BaseModel):
    gate_name: str = Field(min_length=2, max_length=50)
    location: str = Field(min_length=2, max_length=100)
    type: Literal["ENTRY", "EXIT", "BIDIRECTIONAL"] = "ENTRY"
    status: Literal["ACTIVE", "INACTIVE", "MAINTENANCE"] = "ACTIVE"


class ScanIn(BaseModel):
    card_no: str = Field(min_length=3, max_length=20)
    gate_id: int = Field(gt=0)
    scan_time: Optional[datetime] = None


Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
IncidentStatus = Literal["OPEN", "INVESTIGATING", "RESOLVED", "FALSE_ALARM"]
Method = Literal["MANUAL_HEADCOUNT", "GUARD_PATROL", "TURNSTILE_COUNTER", "SIMULATED"]


class TailgatingIn(BaseModel):
    """A guard reports more people than authorised scans -> incident + observation + alert."""
    scan_id: int = Field(gt=0)
    observed_count: int = Field(ge=1, le=100)
    authorized_count: Optional[int] = Field(default=None, ge=0, le=100)  # None -> computed by SQL
    method: Method = "MANUAL_HEADCOUNT"
    notes: str = Field(default="", max_length=500)


class IncidentUpdate(BaseModel):
    severity: Severity
    status: IncidentStatus


class IncidentStatusIn(BaseModel):
    status: IncidentStatus


# ---------------- MongoDB documents ----------------
class ObservationIn(BaseModel):
    incident_id: int = Field(gt=0)
    method: Method = "MANUAL_HEADCOUNT"
    observed_count: int = Field(ge=0, le=100)
    authorized_count: int = Field(ge=0, le=100)
    notes: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)


class ObservationUpdate(BaseModel):
    method: Method
    observed_count: int = Field(ge=0, le=100)
    authorized_count: int = Field(ge=0, le=100)
    notes: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)


class Attachment(BaseModel):
    file_name: str = Field(min_length=1, max_length=120)
    file_type: str = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=200)


class ReportIn(BaseModel):
    incident_id: int = Field(gt=0)
    description: str = Field(min_length=10, max_length=2000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=10)


class ReportUpdate(BaseModel):
    description: str = Field(min_length=10, max_length=2000)


AlertType = Literal["TAILGATING", "ESCALATION", "REPEAT_OFFENDER", "SYSTEM"]


class AlertIn(BaseModel):
    incident_id: int = Field(gt=0)
    alert_type: AlertType = "TAILGATING"
    message: str = Field(min_length=5, max_length=300)
    recipients: list[str] = Field(default_factory=lambda: ["security-desk"], max_length=10)


class AlertUpdate(BaseModel):
    alert_type: AlertType
    message: str = Field(min_length=5, max_length=300)


class AckIn(BaseModel):
    comment: str = Field(default="", max_length=200)
