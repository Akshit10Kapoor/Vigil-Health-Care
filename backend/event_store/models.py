import datetime
import uuid
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, Index, JSON, Uuid
)
from sqlalchemy.orm import relationship
from backend.event_store.database import Base

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

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)

    event_type = Column(String(64), nullable=False, index=True)
    patient_id = Column(String(64), ForeignKey("patients.patient_id"), nullable=False, index=True)
    ward_id = Column(String(64), ForeignKey("wards.ward_id"), nullable=False, index=True)
    bed_number = Column(String(32), nullable=True)
    staff_id = Column(String(64), ForeignKey("staff.staff_id"), nullable=False)
    device_timestamp = Column(DateTime(timezone=True), nullable=False)
    device_tz_offset = Column(String(16), nullable=False, default="+05:30")
    ingested_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    payload = Column(JSON, nullable=False)
    raw_note = Column(Text, nullable=True)
    client_sync_id = Column(String(128), unique=True, nullable=False, index=True)
    metadata_info = Column("metadata", JSON, nullable=True)

    patient = relationship("PatientModel", back_populates="events")
    ward = relationship("WardModel", back_populates="events")
    staff = relationship("StaffModel", back_populates="events")


class AgentAuditLogModel(Base):
    __tablename__ = "agent_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_name = Column(String(64), nullable=False)

    event_id = Column(Uuid(as_uuid=True), ForeignKey("clinical_events.event_id"), nullable=True)
    action = Column(String(128), nullable=False)
    input_state = Column(JSON, nullable=True)
    output_decision = Column(JSON, nullable=True)
    model_or_rule_version = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
