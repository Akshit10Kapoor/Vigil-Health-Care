import os
import sys
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.event_store.database import engine, Base, SessionLocal
from backend.event_store.integrity import (
    append_clinical_event,
    ensure_chain_state,
    install_integrity_triggers,
    verify_chain,
)
from backend.event_store.models import (
    StaffModel, WardModel, PatientModel, ClinicalEventModel, AgentAuditLogModel
)
from backend.orchestration.orchestrator import trigger_verification_pipeline
from backend.orchestration.evidence_agent.agent import EvidenceAgent
from backend.config.settings import settings
from backend.api.middleware.access_control import get_password_hash
from backend.scripts.migrate_integrity import apply_app_role_grants

def clear_and_seed():
    if settings.ENVIRONMENT == "production" and os.getenv("VIGIL_ALLOW_DEMO_RESET") != "1":
        raise SystemExit(
            "Refusing to reset the database in production. "
            "Set VIGIL_ALLOW_DEMO_RESET=1 only on a disposable demo instance."
        )
    if not settings.SEED_DEMO_PASSWORD:
        raise SystemExit("Set VIGIL_SEED_DEMO_PASSWORD before running the demo seeder")

    owner_url = (
        os.getenv("MIGRATION_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
        or settings.DATABASE_URL
    )
    owner_engine = create_engine(owner_url, pool_pre_ping=True)
    app_role = os.getenv("VIGIL_APP_DB_ROLE", "vigil_app").strip() or "vigil_app"
    app_password = os.getenv("VIGIL_APP_DB_PASSWORD", "")
    separate_app_role = owner_engine.url.username != app_role
    if separate_app_role and not app_password:
        raise SystemExit(
            "Set VIGIL_APP_DB_PASSWORD to restore grants for the application role"
        )

    print("Dropping all tables and views...")
    with owner_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    print("Creating all tables...")
    Base.metadata.create_all(bind=owner_engine)
    install_integrity_triggers(owner_engine)

    owner_db = SessionLocal(bind=owner_engine)
    try:
        ensure_chain_state(owner_db)
    finally:
        owner_db.close()

    if separate_app_role:
        apply_app_role_grants(owner_engine, app_role, app_password)

    db = SessionLocal()

    wards = [
        WardModel(ward_id="ICU_01", name="Intensive Care Unit 1", acuity_level="high", capacity=10),
        WardModel(ward_id="SURG_3A", name="Surgical Ward 3A", acuity_level="medium", capacity=20),
        WardModel(ward_id="GEN_01", name="General Ward 1", acuity_level="low", capacity=30)
    ]
    db.add_all(wards)

    demo_hash = get_password_hash(settings.SEED_DEMO_PASSWORD)
    admin_password = settings.SEED_ADMIN_PASSWORD or settings.SEED_DEMO_PASSWORD
    staff_members = [
        StaffModel(staff_id="NURSE_101", full_name="Anjali Sharma", role="nurse", hashed_password=demo_hash, assigned_ward_id="ICU_01"),
        StaffModel(staff_id="NURSE_102", full_name="Rajesh Kumar", role="nurse", hashed_password=demo_hash, assigned_ward_id="SURG_3A"),
        StaffModel(staff_id="ADMIN_01", full_name="Dr. Gupta", role="admin", hashed_password=get_password_hash(admin_password))
    ]
    db.add_all(staff_members)

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

    event1 = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_001",
        ward_id="ICU_01",
        staff_id="NURSE_101",
        device_timestamp=now - timedelta(hours=4),
        payload={"vitals": {"bp": "110/70", "hr": 88}},
        client_sync_id="sync_mock_1"
    )

    event2 = ClinicalEventModel(
        event_type="medication_order_documentation",
        patient_id="PAT_002",
        ward_id="ICU_01",
        staff_id="NURSE_101",
        device_timestamp=now - timedelta(minutes=30),
        payload={
            "medication_name": "Insulin Regular",
            "dosage": "10 units IV",
            "verifying_nurse_id": "NURSE_102"
        },
        client_sync_id="sync_mock_2"
    )

    event4 = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_004",
        ward_id="SURG_3A",
        staff_id="NURSE_102",
        device_timestamp=now - timedelta(hours=7, minutes=30),
        payload={"vitals": {"bp": "130/85", "hr": 72}},
        client_sync_id="sync_mock_4"
    )

    event5 = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_005",
        ward_id="GEN_01",
        staff_id="NURSE_101",
        device_timestamp=now - timedelta(hours=1),
        payload={"vitals": {"bp": "120/80", "hr": 75}},
        client_sync_id="sync_mock_5"
    )

    for event in (event1, event2, event4, event5):
        append_clinical_event(db, event)
    db.commit()

    print("Running Gap Detection Pipeline...")
    trigger_verification_pipeline()

    print("Running Evidence Generation...")
    db.commit()
    ev_agent = EvidenceAgent()
    ev_agent.process_closed_gaps(db)

    verification = verify_chain(db)
    if not verification.valid:
        raise SystemExit(
            "Seeded data failed integrity verification: " + str(verification.reason)
        )
    db.close()
    owner_engine.dispose()
    print("Database cleared and seeded with 5 detailed scenarios!")

if __name__ == "__main__":
    clear_and_seed()
