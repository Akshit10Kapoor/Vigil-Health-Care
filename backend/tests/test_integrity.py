import datetime
import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.event_store.database import engine
from backend.event_store.integrity import (
    GENESIS_HASH,
    ChainIntegrityError,
    append_clinical_event,
    clear_integrity_failure,
    compute_event_hash,
    get_chain_state,
    install_integrity_triggers,
    mark_integrity_failure,
    verify_chain,
)
from backend.event_store.models import ChainVerificationLogModel, ClinicalEventModel

PAYLOAD = {
    "vitals": {"bp": "120/80", "spo2": 98, "pulse": 72},
    "position_change": "Left lateral",
    "iv_site_check": "Clean",
}


def _event_body(sync_id, event_type="nursing_round", payload=None, **overrides):
    body = {
        "client_sync_id": sync_id,
        "event_type": event_type,
        "patient_id": "PAT_1001",
        "ward_id": "ICU_01",
        "bed_number": "Bed-01",
        "staff_id": "NURSE_101",
        "device_timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "device_tz_offset": "+05:30",
        "payload": payload if payload is not None else dict(PAYLOAD),
    }
    body.update(overrides)
    return body


def _ingest(client, sync_id, event_type="nursing_round", payload=None, **overrides):
    response = client.post(
        "/api/v1/events/ingest",
        json={"events": [_event_body(sync_id, event_type, payload, **overrides)]},
    )
    assert response.status_code == 200, response.text
    return response.json()["results"][0]


def _make_direct(sync_id, payload=None):
    return ClinicalEventModel(
        event_id=uuid.uuid4(),
        event_type="nursing_round",
        patient_id="PAT_1001",
        ward_id="ICU_01",
        bed_number="Bed-01",
        staff_id="NURSE_101",
        device_timestamp=datetime.datetime.now(datetime.timezone.utc),
        device_tz_offset="+05:30",
        payload=payload if payload is not None else dict(PAYLOAD),
        client_sync_id=sync_id,
    )


def _append_direct(db, sync_id, payload=None):
    event = _make_direct(sync_id, payload)
    append_clinical_event(db, event)
    db.commit()
    return event


def _drop_trigger(db, name, table="clinical_events"):
    if engine.dialect.name == "postgresql":
        db.execute(text(f"DROP TRIGGER IF EXISTS {name} ON {table}"))
    else:
        db.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
    db.commit()


def _restore_triggers():
    install_integrity_triggers(engine)


def test_valid_chain_and_verification_api(client, admin_headers, nurse_headers, db):
    first = _ingest(client, "integrity_valid_1")
    second = _ingest(client, "integrity_valid_2")
    assert first["status"] == "success"
    assert second["status"] == "success"

    db.expire_all()
    result = verify_chain(db)
    assert result.valid is True
    assert result.events_checked == 2
    assert result.reason is None

    events = (
        db.query(ClinicalEventModel)
        .order_by(ClinicalEventModel.id)
        .all()
    )
    assert events[0].prev_hash == GENESIS_HASH
    assert events[1].prev_hash == events[0].event_hash
    state = get_chain_state(db)
    assert state.last_event_id == events[1].id
    assert state.last_hash == events[1].event_hash

    status = client.get("/api/v1/integrity/chain", headers=admin_headers)
    assert status.status_code == 200
    body = status.json()
    assert body["valid"] is True
    assert body["events_checked"] == 2
    assert "Ramesh Verma" not in json.dumps(body)

    forbidden = client.get("/api/v1/integrity/chain", headers=nurse_headers)
    assert forbidden.status_code == 403


def test_verification_endpoint_records_append_only_log(client, admin_headers, db):
    _ingest(client, "integrity_record_1")

    response = client.post(
        "/api/v1/integrity/chain/verify", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True

    db.expire_all()
    log = db.query(ChainVerificationLogModel).one()
    assert log.valid is True
    assert log.events_checked == 1

    with pytest.raises(SQLAlchemyError) as exc:
        db.execute(
            text(
                "UPDATE chain_verification_logs SET reason = 'forged' "
                "WHERE id = :log_id"
            ),
            {"log_id": log.id},
        )
        db.commit()
    assert "append-only" in str(exc.value).lower()
    db.rollback()


def test_update_and_delete_are_blocked(client, db):
    _ingest(client, "integrity_block_1")
    db.expire_all()
    event = db.query(ClinicalEventModel).one()

    with pytest.raises(SQLAlchemyError) as update_exc:
        db.query(ClinicalEventModel).filter(
            ClinicalEventModel.event_id == event.event_id
        ).update({ClinicalEventModel.payload: {}}, synchronize_session=False)
        db.commit()
    assert "append-only" in str(update_exc.value).lower()
    db.rollback()

    with pytest.raises(SQLAlchemyError) as delete_exc:
        db.query(ClinicalEventModel).filter(
            ClinicalEventModel.event_id == event.event_id
        ).delete(synchronize_session=False)
        db.commit()
    assert "append-only" in str(delete_exc.value).lower()
    db.rollback()


def test_wrong_prev_hash_is_rejected_by_database(client, db):
    _ingest(client, "integrity_prev_1")
    db.expire_all()
    event = _make_direct("integrity_prev_bad")
    event.ingested_at = datetime.datetime.now(datetime.timezone.utc)
    event.prev_hash = "f" * 64
    event.event_hash = compute_event_hash(event, event.prev_hash)
    db.add(event)

    with pytest.raises(SQLAlchemyError) as exc:
        db.commit()
    assert "prev_hash" in str(exc.value).lower()
    db.rollback()

    db.expire_all()
    result = verify_chain(db)
    assert result.valid is True
    assert result.events_checked == 1


def test_forged_event_hash_is_detected(db):
    event = _make_direct("integrity_forged_hash")
    event.ingested_at = datetime.datetime.now(datetime.timezone.utc)
    state = get_chain_state(db)
    event.prev_hash = state.last_hash
    event.event_hash = "f" * 64
    db.add(event)
    db.commit()

    db.expire_all()
    result = verify_chain(db)
    assert result.valid is False
    assert result.reason == "event_hash_mismatch"
    assert result.first_invalid_position == 1
    assert result.first_invalid_event_id == event.event_id


def test_payload_tamper_is_detected(client, db):
    result = _ingest(client, "integrity_tamper_1")
    _drop_trigger(db, "trg_clinical_events_no_update")

    db.query(ClinicalEventModel).filter(
        ClinicalEventModel.event_id == uuid.UUID(result["event_id"])
    ).update(
        {ClinicalEventModel.payload: {"vitals": {"hr": 999}}},
        synchronize_session=False,
    )
    db.commit()
    _restore_triggers()

    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is False
    assert verification.reason == "event_hash_mismatch"
    assert verification.first_invalid_position == 1


def test_middle_event_deletion_is_detected(db):
    _append_direct(db, "integrity_delete_middle_1")
    middle = _append_direct(db, "integrity_delete_middle_2")
    third = _append_direct(db, "integrity_delete_middle_3")
    _drop_trigger(db, "trg_clinical_events_no_delete")

    db.query(ClinicalEventModel).filter(
        ClinicalEventModel.event_id == middle.event_id
    ).delete(synchronize_session=False)
    db.commit()
    _restore_triggers()

    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is False
    assert verification.reason == "prev_hash_mismatch"
    assert verification.first_invalid_event_id == third.event_id
    assert verification.first_invalid_position == 2


def test_tail_deletion_is_detected(db):
    _append_direct(db, "integrity_delete_tail_1")
    last = _append_direct(db, "integrity_delete_tail_2")
    _drop_trigger(db, "trg_clinical_events_no_delete")

    if engine.dialect.name == "postgresql":
        db.execute(
            text(
                "ALTER TABLE event_chain_state "
                "DROP CONSTRAINT IF EXISTS fk_event_chain_state_last_event_id"
            )
        )
        db.commit()

    db.query(ClinicalEventModel).filter(
        ClinicalEventModel.event_id == last.event_id
    ).delete(synchronize_session=False)
    db.commit()
    _restore_triggers()

    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is False
    assert verification.reason == "chain_head_mismatch"


def test_reordered_event_ids_are_detected(db):
    _append_direct(db, "integrity_reorder_1")
    middle = _append_direct(db, "integrity_reorder_2")
    _append_direct(db, "integrity_reorder_3")
    _drop_trigger(db, "trg_clinical_events_no_update")

    db.query(ClinicalEventModel).filter(
        ClinicalEventModel.event_id == middle.event_id
    ).update({ClinicalEventModel.id: 100}, synchronize_session=False)
    db.commit()
    _restore_triggers()

    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is False
    assert verification.reason == "prev_hash_mismatch"


def test_missing_chain_head_trigger_is_not_silently_accepted(db):
    _drop_trigger(db, "trg_clinical_events_chain_head")
    event = _make_direct("integrity_missing_trigger")

    with pytest.raises(ChainIntegrityError):
        append_clinical_event(db, event)
    db.rollback()
    _restore_triggers()

    db.expire_all()
    result = verify_chain(db)
    assert result.valid is True
    assert result.events_checked == 0


def test_transaction_rollback_does_not_extend_chain(db):
    event = _make_direct("integrity_rollback")
    append_clinical_event(db, event)
    db.rollback()

    db.expire_all()
    result = verify_chain(db)
    assert result.valid is True
    assert result.events_checked == 0

    _append_direct(db, "integrity_rollback_2")
    db.expire_all()
    result = verify_chain(db)
    assert result.valid is True
    assert result.events_checked == 1


def test_duplicate_sync_id_does_not_extend_chain(client, db):
    first = _ingest(client, "integrity_duplicate_1")
    second = _ingest(client, "integrity_duplicate_1")
    assert first["status"] == "success"
    assert second["status"] == "duplicate"

    db.expire_all()
    result = verify_chain(db)
    assert result.valid is True
    assert result.events_checked == 1


def test_correction_is_additive_and_chain_verifies(client, db):
    original = _ingest(client, "integrity_correction_original")
    correction = _ingest(
        client,
        "integrity_correction_fix",
        event_type="clinical_event_correction",
        payload={"corrected": {"spo2": 97}},
        corrects_event_id=original["event_id"],
        correction_reason="Corrected SpO2 transcription error",
    )
    assert correction["status"] == "success"

    db.expire_all()
    original_row = (
        db.query(ClinicalEventModel)
        .filter(ClinicalEventModel.event_id == uuid.UUID(original["event_id"]))
        .one()
    )
    correction_row = (
        db.query(ClinicalEventModel)
        .filter(ClinicalEventModel.event_id == uuid.UUID(correction["event_id"]))
        .one()
    )
    assert original_row.payload["vitals"]["spo2"] == 98
    assert correction_row.corrects_event_id == original_row.event_id
    assert "transcription" in correction_row.correction_reason

    verification = verify_chain(db)
    assert verification.valid is True
    assert verification.events_checked == 2


def test_correction_requires_reason_and_existing_target(client, db):
    original = _ingest(client, "integrity_correction_validation")

    missing_reason = _ingest(
        client,
        "integrity_correction_no_reason",
        event_type="clinical_event_correction",
        payload={"corrected": {}},
        corrects_event_id=original["event_id"],
    )
    assert missing_reason["status"] == "error"
    assert "correction_reason" in missing_reason["error_message"]

    missing_target = _ingest(
        client,
        "integrity_correction_no_target",
        event_type="clinical_event_correction",
        payload={"corrected": {}},
        corrects_event_id=str(uuid.uuid4()),
        correction_reason="Attempted correction",
    )
    assert missing_target["status"] == "error"
    assert "not found" in missing_target["error_message"]

    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is True
    assert verification.events_checked == 1


def test_ingestion_is_halted_after_integrity_failure(db):
    mark_integrity_failure("unit-test failure")
    try:
        event = _make_direct("integrity_guard_halt")
        with pytest.raises(ChainIntegrityError) as exc:
            append_clinical_event(db, event)
        assert "halted" in str(exc.value).lower()
        db.rollback()
    finally:
        clear_integrity_failure()

    _append_direct(db, "integrity_guard_recovered")
    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is True
    assert verification.events_checked == 1


def test_naive_device_timestamp_is_hashed_consistently(client, db):
    result = _ingest(
        client,
        "integrity_naive_timestamp",
        device_timestamp="2026-10-21T10:00:00",
    )
    assert result["status"] == "success"

    db.expire_all()
    verification = verify_chain(db)
    assert verification.valid is True
    assert verification.events_checked == 1


def test_column_defaults_are_hashed_as_stored(db):
    event = ClinicalEventModel(
        event_id=uuid.uuid4(),
        event_type="nursing_round",
        patient_id="PAT_1001",
        ward_id="ICU_01",
        staff_id="NURSE_101",
        device_timestamp=datetime.datetime.now(datetime.timezone.utc),
        payload={"vitals": {"hr": 80}},
        client_sync_id="integrity_default_tz",
    )
    assert event.device_tz_offset is None
    append_clinical_event(db, event)
    db.commit()

    db.expire_all()
    stored = db.query(ClinicalEventModel).filter(
        ClinicalEventModel.client_sync_id == "integrity_default_tz"
    ).one()
    assert stored.device_tz_offset == "+05:30"
    verification = verify_chain(db)
    assert verification.valid is True
    assert verification.events_checked == 1
