import datetime
import uuid
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, Index, JSON, Uuid,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.event_store.database import Base

# JSONB on PostgreSQL matches backend/event_store/schema/init_db.sql. Using the
# generic JSON type there would store payloads as raw text and make the ORM
# and production read numbers differently, which breaks hash verification.
JSON_COLUMN_TYPE = JSON().with_variant(JSONB(), "postgresql")

# Hash canonicalization version written for every newly appended event.
# 1 = original json.dumps canonical form (kept only to verify rows written by
#     earlier builds; never written by new code).
# 2 = normalized number form that survives JSONB round-trips.
CANONICAL_HASH_VERSION = 2


def _event_pk_type():
    # BIGSERIAL in PostgreSQL, INTEGER PRIMARY KEY AUTOINCREMENT-compatible in SQLite.
    return BigInteger().with_variant(Integer, "sqlite")


class WardModel(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    acuity_level = Column(String(32), nullable=False, default="medium")
    capacity = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    staff_members = relationship("StaffModel", back_populates="assigned_ward")
    patients = relationship("PatientModel", back_populates="ward")
    events = relationship("ClinicalEventModel", back_populates="ward")


class StaffModel(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False) # 'nurse', 'ward_manager', 'quality_team', 'admin'
    hashed_password = Column(String(256), nullable=False)
    assigned_ward_id = Column(String(64), ForeignKey("wards.ward_id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    assigned_ward = relationship("WardModel", back_populates="staff_members")
    events = relationship("ClinicalEventModel", back_populates="staff")


class PatientModel(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(16), nullable=True)
    bed_number = Column(String(32), nullable=False)
    ward_id = Column(String(64), ForeignKey("wards.ward_id"), nullable=False)
    admission_date = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    acuity_level = Column(String(32), default="medium")
    status = Column(String(32), default="admitted") # 'admitted', 'discharged'
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    ward = relationship("WardModel", back_populates="patients")
    events = relationship("ClinicalEventModel", back_populates="patient")


class ClinicalEventModel(Base):
    __tablename__ = "clinical_events"
    __table_args__ = (
        UniqueConstraint("prev_hash", name="uq_clinical_events_prev_hash"),
        UniqueConstraint("event_hash", name="uq_clinical_events_event_hash"),
        Index("ix_clinical_events_corrects_event_id", "corrects_event_id"),
    )

    id = Column(_event_pk_type(), primary_key=True, index=True, autoincrement=True)
    event_id = Column(Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)

    event_type = Column(String(64), nullable=False, index=True)
    patient_id = Column(String(64), ForeignKey("patients.patient_id"), nullable=False, index=True)
    ward_id = Column(String(64), ForeignKey("wards.ward_id"), nullable=False, index=True)
    bed_number = Column(String(32), nullable=True)
    staff_id = Column(String(64), ForeignKey("staff.staff_id"), nullable=False)
    device_timestamp = Column(DateTime(timezone=True), nullable=False)
    device_tz_offset = Column(String(16), nullable=False, default="+05:30")
    ingested_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    payload = Column(JSON_COLUMN_TYPE, nullable=False)
    raw_note = Column(Text, nullable=True)
    client_sync_id = Column(String(128), unique=True, nullable=False, index=True)
    metadata_info = Column("metadata", JSON_COLUMN_TYPE, nullable=True)

    # Tamper-evident chain. Both hashes are SHA-256 hex digests. For the first
    # event prev_hash is GENESIS_HASH and no other event may reuse it.
    prev_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), unique=True, nullable=False)
    # Which canonicalization produced event_hash. Rows written before the
    # version column existed are version 1 (see migrate_integrity).
    hash_version = Column(
        Integer, nullable=False, default=CANONICAL_HASH_VERSION
    )

    # Corrections are additive events. The original row is never modified.
    corrects_event_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("clinical_events.event_id", name="fk_clinical_events_corrects_event_id"),
        nullable=True,
    )
    correction_reason = Column(Text, nullable=True)

    patient = relationship("PatientModel", back_populates="events")
    ward = relationship("WardModel", back_populates="events")
    staff = relationship("StaffModel", back_populates="events")


class AgentAuditLogModel(Base):
    __tablename__ = "agent_audit_logs"

    id = Column(_event_pk_type(), primary_key=True, index=True, autoincrement=True)
    agent_name = Column(String(64), nullable=False)

    event_id = Column(Uuid(as_uuid=True), ForeignKey("clinical_events.event_id"), nullable=True)
    action = Column(String(128), nullable=False)
    input_state = Column(JSON, nullable=True)
    output_decision = Column(JSON, nullable=True)
    model_or_rule_version = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)


class EventChainStateModel(Base):
    """Single authoritative chain head per event stream.

    The head row is updated by a database trigger owned by the migration role,
    not by the application role. Keeping the head in the database is what lets
    verification detect deletion of the newest events, not just edits to the
    remaining rows.
    """
    __tablename__ = "event_chain_state"

    chain_id = Column(String(64), primary_key=True)
    last_event_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("clinical_events.id", name="fk_event_chain_state_last_event_id"),
        nullable=True,
    )
    last_hash = Column(String(64), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ChainVerificationLogModel(Base):
    __tablename__ = "chain_verification_logs"

    id = Column(_event_pk_type(), primary_key=True, index=True, autoincrement=True)
    chain_id = Column(String(64), nullable=False, index=True)
    checked_at = Column(DateTime(timezone=True), nullable=False)
    valid = Column(Boolean, nullable=False)
    events_checked = Column(Integer, nullable=False, default=0)
    first_invalid_event_id = Column(Uuid(as_uuid=True), nullable=True)
    first_invalid_position = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    head_hash = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    verifier_version = Column(String(64), nullable=False)
