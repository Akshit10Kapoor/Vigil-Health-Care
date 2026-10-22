import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.event_store.database import Base
from backend.event_store.integrity import (
    append_clinical_event,
    ensure_chain_state,
    install_integrity_triggers,
)
from backend.event_store.models import PatientModel, WardModel, ClinicalEventModel
from backend.orchestration.expectation_agent.agent import ExpectationAgent

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    state_session = TestingSessionLocal()
    try:
        ensure_chain_state(state_session)
    finally:
        state_session.close()
    install_integrity_triggers(engine)
    db = TestingSessionLocal()

    ward = WardModel(ward_id="ICU_01", name="Intensive Care", acuity_level="high")
    patient = PatientModel(patient_id="PAT_001", full_name="John Doe", bed_number="1", ward_id="ICU_01", status="admitted")
    patient.admission_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)

    db.add(ward)
    db.add(patient)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)

def test_expectation_agent_no_events_overdue(db_session):
    agent = ExpectationAgent()
    current_time = datetime.datetime.now(datetime.timezone.utc)

    gaps = agent.evaluate_gaps(db_session, current_time)

    assert len(gaps) > 0
    icu_gap = next((g for g in gaps if g.rule_id == "icu_vitals_2h"), None)
    assert icu_gap is not None
    assert icu_gap.patient_id == "PAT_001"
    assert icu_gap.overdue_by_mins > 0

def test_expectation_agent_with_recent_event(db_session):
    agent = ExpectationAgent()
    current_time = datetime.datetime.now(datetime.timezone.utc)

    recent_event = ClinicalEventModel(
        event_type="nursing_round",
        patient_id="PAT_001",
        ward_id="ICU_01",
        staff_id="NURSE_01",
        device_timestamp=current_time - datetime.timedelta(hours=1),
        payload={"vitals": {"hr": 80}},
        client_sync_id="test-sync-id-123"
    )
    append_clinical_event(db_session, recent_event)
    db_session.commit()

    gaps = agent.evaluate_gaps(db_session, current_time)

    icu_gap = next((g for g in gaps if g.rule_id == "icu_vitals_2h"), None)
    assert icu_gap is None
