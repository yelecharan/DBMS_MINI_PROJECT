import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, Integer, Float, DateTime, ForeignKey, 
    Text, JSON, UniqueConstraint, CheckConstraint, Index, TypeDecorator
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import relationship
from app.database.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UUIDString(TypeDecorator):
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=False))
        return dialect.type_descriptor(String(36))


class User(Base):
    __tablename__ = "users"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False) # ADMIN, SECURITY_OFFICER, AUDITOR
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    assigned_incidents = relationship("Incident", back_populates="assignee", foreign_keys="Incident.assigned_to")
    actions = relationship("IncidentAction", back_populates="actor")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    employee_code = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    department = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    credentials = relationship("AccessCredential", back_populates="employee", cascade="all, delete-orphan")


class Site(Base):
    __tablename__ = "sites"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    site_name = Column(String(255), unique=True, nullable=False)
    address = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    zones = relationship("Zone", back_populates="site", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    site_id = Column(UUIDString(), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    parent_zone_id = Column(UUIDString(), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True)
    zone_name = Column(String(255), nullable=False)
    zone_type = Column(String(100), nullable=False)
    sensitivity_level = Column(Integer, default=5, nullable=False) # 1 to 50
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    site = relationship("Site", back_populates="zones")
    parent_zone = relationship("Zone", remote_side=[id], backref="sub_zones")
    gates = relationship("Gate", back_populates="zone", cascade="all, delete-orphan")


class Gate(Base):
    __tablename__ = "gates"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    zone_id = Column(UUIDString(), ForeignKey("zones.id", ondelete="CASCADE"), nullable=False)
    gate_code = Column(String(50), unique=True, nullable=False, index=True)
    gate_name = Column(String(255), nullable=False)
    direction = Column(String(20), default="ENTRY", nullable=False) # ENTRY, EXIT, BIDIRECTIONAL
    is_active = Column(Boolean, default=True, nullable=False)
    session_window_seconds = Column(Integer, default=8, nullable=False)
    minimum_detection_confidence = Column(Float, default=0.65, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    zone = relationship("Zone", back_populates="gates")
    cameras = relationship("Camera", back_populates="gate", cascade="all, delete-orphan")
    access_events = relationship("AccessEvent", back_populates="gate", cascade="all, delete-orphan")
    gate_sessions = relationship("GateSession", back_populates="gate", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="gate", cascade="all, delete-orphan")
    detection_rules = relationship("DetectionRule", back_populates="gate", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    gate_id = Column(UUIDString(), ForeignKey("gates.id", ondelete="CASCADE"), nullable=False)
    camera_code = Column(String(50), unique=True, nullable=False, index=True)
    camera_name = Column(String(255), nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    gate = relationship("Gate", back_populates="cameras")
    observations = relationship("CameraObservation", back_populates="camera", cascade="all, delete-orphan")


class AccessCredential(Base):
    __tablename__ = "access_credentials"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    employee_id = Column(UUIDString(), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    credential_hash = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), default="ACTIVE", nullable=False) # ACTIVE, REVOKED, EXPIRED
    valid_from = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="credentials")
    access_events = relationship("AccessEvent", back_populates="credential")


class AccessEvent(Base):
    __tablename__ = "access_events"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    gate_id = Column(UUIDString(), ForeignKey("gates.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(UUIDString(), ForeignKey("access_credentials.id", ondelete="SET NULL"), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    direction = Column(String(20), default="ENTRY", nullable=False)
    decision = Column(String(20), nullable=False) # GRANTED, DENIED
    denial_reason = Column(String(255), nullable=True)
    external_event_id = Column(String(100), unique=True, nullable=True)

    # Relationships
    gate = relationship("Gate", back_populates="access_events")
    credential = relationship("AccessCredential", back_populates="access_events")


class GateSession(Base):
    __tablename__ = "gate_sessions"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    gate_id = Column(UUIDString(), ForeignKey("gates.id", ondelete="CASCADE"), nullable=False, index=True)
    opened_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    closes_at = Column(DateTime(timezone=True), nullable=False)
    expected_authorized_entries = Column(Integer, default=0, nullable=False)
    observed_crossings = Column(Integer, default=0, nullable=False)
    unmatched_crossings = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="OPEN", nullable=False) # OPEN, FINALIZED, CANCELLED
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    gate = relationship("Gate", back_populates="gate_sessions")
    observations = relationship("CameraObservation", back_populates="gate_session")
    incidents = relationship("Incident", back_populates="gate_session")


class CameraObservation(Base):
    __tablename__ = "camera_observations"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    gate_id = Column(UUIDString(), ForeignKey("gates.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(UUIDString(), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    gate_session_id = Column(UUIDString(), ForeignKey("gate_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    tracker_id = Column(String(100), nullable=False, index=True) # Anonymous ByteTrack ID
    observed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    direction = Column(String(20), default="ENTRY", nullable=False)
    confidence = Column(Float, nullable=False)
    evidence_reference = Column(String(255), nullable=True)
    external_event_id = Column(String(100), unique=True, nullable=True)

    # Relationships
    gate = relationship("Gate")
    camera = relationship("Camera", back_populates="observations")
    gate_session = relationship("GateSession", back_populates="observations")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("gate_session_id", name="uq_incidents_gate_session"),
    )

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    gate_id = Column(UUIDString(), ForeignKey("gates.id", ondelete="CASCADE"), nullable=False, index=True)
    gate_session_id = Column(UUIDString(), ForeignKey("gate_sessions.id", ondelete="SET NULL"), nullable=True)
    incident_type = Column(String(50), nullable=False) # TAILGATING, UNAUTHORIZED_ENTRY, etc.
    authorized_count = Column(Integer, nullable=False)
    observed_count = Column(Integer, nullable=False)
    unmatched_count = Column(Integer, nullable=False)
    average_confidence = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, index=True) # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(50), default="NEW", nullable=False, index=True) # NEW, ACKNOWLEDGED, UNDER_INVESTIGATION, RESOLVED, FALSE_POSITIVE
    summary = Column(Text, nullable=False)
    assigned_to = Column(UUIDString(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    gate = relationship("Gate", back_populates="incidents")
    gate_session = relationship("GateSession", back_populates="incidents")
    assignee = relationship("User", back_populates="assigned_incidents", foreign_keys=[assigned_to])
    actions = relationship("IncidentAction", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentAction.created_at.desc()")
    evidence = relationship("EvidenceAsset", back_populates="incident", cascade="all, delete-orphan")


class IncidentAction(Base):
    __tablename__ = "incident_actions"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    incident_id = Column(UUIDString(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(UUIDString(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    action_type = Column(String(50), nullable=False) # ACKNOWLEDGE, ASSIGN, NOTE, RESOLVE, FALSE_POSITIVE
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    incident = relationship("Incident", back_populates="actions")
    actor = relationship("User", back_populates="actions")


class EvidenceAsset(Base):
    __tablename__ = "evidence_assets"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    incident_id = Column(UUIDString(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    object_reference = Column(String(255), nullable=False)
    media_type = Column(String(50), default="IMAGE_CROPPED", nullable=False)
    checksum = Column(String(64), nullable=False)
    is_redacted = Column(Boolean, default=True, nullable=False)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    incident = relationship("Incident", back_populates="evidence")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    actor_user_id = Column(UUIDString(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class DetectionRule(Base):
    __tablename__ = "detection_rules"

    id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    gate_id = Column(UUIDString(), ForeignKey("gates.id", ondelete="CASCADE"), nullable=True)
    rule_name = Column(String(100), nullable=False)
    confidence_threshold = Column(Float, default=0.65, nullable=False)
    session_window_seconds = Column(Integer, default=8, nullable=False)
    zone_sensitivity_bonus = Column(Integer, default=15, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    gate = relationship("Gate", back_populates="detection_rules")


class IncidentVectorOutbox(Base):
    __tablename__ = "incident_vector_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="ck_incident_vector_outbox_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_incident_vector_outbox_attempts"),
        Index("ix_incident_vector_outbox_ready", "status", "next_attempt_at", "created_at"),
        Index("ix_incident_vector_outbox_incident_event", "incident_id", "event_type"),
    )

    event_id = Column(UUIDString(), primary_key=True, default=generate_uuid)
    incident_id = Column(
        UUIDString(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    event_type = Column(String(80), nullable=False, default="INCIDENT_CREATED")
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
