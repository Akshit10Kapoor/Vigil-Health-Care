import os
import sys
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

# Add the project root to python path so we can import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.event_store.database import engine, Base, SessionLocal
from backend.event_store.models import (
    StaffModel, WardModel, PatientModel, ClinicalEventModel, AgentAuditLogModel
)
from backend.orchestration.orchestrator import trigger_verification_pipeline
from backend.orchestration.evidence_agent.agent import EvidenceAgent

def clear_and_seed():
    print("Dropping all tables and views...")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # 1. Create Wards
    wards = [
        WardModel(ward_id="ICU_01", name="Intensive Care Unit 1", acuity_level="high", capacity=10),
        WardModel(ward_id="SURG_3A", name="Surgical Ward 3A", acuity_level="medium", capacity=20),
        WardModel(ward_id="GEN_01", name="General Ward 1", acuity_level="low", capacity=30)
    ]
    db.add_all(wards)

    # 2. Create Staff
    staff_members = [
        StaffModel(staff_id="NURSE_101", full_name="Anjali Sharma", role="nurse", hashed_password="mock", assigned_ward_id="ICU_01"),
        StaffModel(staff_id="NURSE_102", full_name="Rajesh Kumar", role="nurse", hashed_password="mock", assigned_ward_id="SURG_3A"),
        StaffModel(staff_id="ADMIN_01", full_name="Dr. Gupta", role="admin", hashed_password="mock")
    ]
    db.add_all(staff_members)

    # 3. Create Patients (5 Patients showing different features)
    now = datetime.now(timezone.utc)
    
    patients = [
        PatientModel(patient_id="PAT_001", full_name="Arjun Mehta", age=45, bed_number="ICU-1", ward_id="ICU_01", acuity_level="high"),
        PatientModel(patient_id="PAT_002", full_name="Sunita Rao", age=62, bed_number="ICU-2", ward_id="ICU_01", acuity_level="high"),
        PatientModel(patient_id="PAT_003", full_name="Vikram Singh", age=33, bed_number="SURG-12", ward_id="SURG_3A", acuity_level="medium"),
        PatientModel(patient_id="PAT_004", full_name="Priya Patel", age=28, bed_number="SURG-14", ward_id="SURG_3A", acuity_level="medium"),
        PatientModel(patient_id="PAT_005", full_name="Ramesh Verma", age=55, bed_number="GEN-4", ward_id="GEN_01", acuity_level="low")
    ]
    db.add_all(patients)
    db.commit()

    print("Populating initial clinical events...")

    # Scenario 1 (PAT_001): Missing ICU Vitals (Urgent Gap)
    # Event logged 4 hours ago. Protocol demands every 2 hours.
    event1 = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_001",
        ward_id="ICU_01",
        staff_id="NURSE_101",
        device_timestamp=now - timedelta(hours=4),
        payload={"vitals": {"bp": "110/70", "hr": 88}},
        client_sync_id="sync_mock_1"
    )
    
    # Scenario 2 (PAT_002): High Alert Medication (Dual verification completed successfully)
    event2 = ClinicalEventModel(
        event_type="medication_order_documentation",
        patient_id="PAT_002",
        ward_id="ICU_01",
        staff_id="NURSE_101",
        device_timestamp=now - timedelta(minutes=30),
        payload={
            "medication_name": "Insulin Regular",
            "dosage": "10 units IV",
            "verifying_nurse_id": "NURSE_102" # Dual verified!
        },
        client_sync_id="sync_mock_2"
    )

    # Scenario 3 (PAT_003): Missing Consent before Surgery (Urgent Gap)
    # Surgery is scheduled (mocked by Expectation Agent later), but no consent logged.
    # We will log NO event for PAT_003 to trigger a missing consent gap.

    # Scenario 4 (PAT_004): Vitals delayed by 1 hour (Routine Gap)
    # Medium acuity needs vitals every 6 hours. Last one was 7.5 hours ago.
    event4 = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_004",
        ward_id="SURG_3A",
        staff_id="NURSE_102",
        device_timestamp=now - timedelta(hours=7, minutes=30),
        payload={"vitals": {"bp": "130/85", "hr": 72}},
        client_sync_id="sync_mock_4"
    )

    # Scenario 5 (PAT_005): Perfectly Compliant
    # Low acuity needs vitals every 12 hours. Last one was 1 hour ago.
    event5 = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_005",
        ward_id="GEN_01",
        staff_id="NURSE_101",
        device_timestamp=now - timedelta(hours=1),
        payload={"vitals": {"bp": "120/80", "hr": 75}},
        client_sync_id="sync_mock_5"
    )

    db.add_all([event1, event2, event4, event5])
    db.commit()

    print("Running Gap Detection Pipeline...")
    trigger_verification_pipeline()

    print("Running Evidence Generation...")
    db.commit()
    ev_agent = EvidenceAgent()
    ev_agent.process_closed_gaps(db)

    print("Database cleared and seeded with 5 detailed scenarios!")

if __name__ == "__main__":
    clear_and_seed()
