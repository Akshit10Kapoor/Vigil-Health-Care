import datetime
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.event_store.database import SessionLocal, engine
from backend.event_store.integrity import (
    CHAIN_ID,
    GENESIS_HASH,
    ChainIntegrityError,
    append_clinical_event,
    compute_event_hash,
    ensure_chain_state,
    integrity_triggers_ready,
    verify_chain,
)
from backend.event_store.models import (
    ClinicalEventModel,
    EventChainStateModel,
)
from backend.scripts.migrate_integrity import apply_app_role_grants, migrate

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="PostgreSQL-specific integrity tests",
)


def _make_event(sync_id):
    return ClinicalEventModel(
        event_id=uuid.uuid4(),
        event_type="nursing_round",
        patient_id="PAT_1001",
        ward_id="ICU_01",
        bed_number="Bed-01",
        staff_id="NURSE_101",
        device_timestamp=datetime.datetime.now(datetime.timezone.utc),
        device_tz_offset="+05:30",
        payload={"vitals": {"hr": 80}},
        client_sync_id=sync_id,
    )


def test_concurrent_appends_are_serialized():
    workers = 5
    barrier = threading.Barrier(workers)

    def worker(index):
        session = SessionLocal()
        try:
            barrier.wait(timeout=10)
            event = _make_event(f"integrity_concurrent_{index}")
            append_clinical_event(session, event)
            session.commit()
            return event.event_id
        except Exception as exc:
            session.rollback()
            return exc
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(worker, range(workers)))

    errors = [result for result in results if isinstance(result, Exception)]
    assert not errors, errors

    session = SessionLocal()
    try:
        verification = verify_chain(session)
    finally:
        session.close()
    assert verification.valid is True
    assert verification.events_checked == workers


def test_application_role_can_append_but_cannot_mutate():
    role = f"vigil_test_app_{uuid.uuid4().hex[:8]}"
    password = "test-app-role-password-123456"

    with engine.connect() as conn:
        is_superuser = conn.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    if not is_superuser:
        pytest.skip("SET ROLE requires a superuser test connection")

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar()
        if exists:
            conn.exec_driver_sql(f'DROP OWNED BY "{role}"')
            conn.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')

    apply_app_role_grants(engine, role, password)
    app_engine = create_engine(
        engine.url.set(username=role, password=password),
        pool_pre_ping=True,
    )

    try:
        app_session = Session(bind=app_engine)
        try:
            event = _make_event("integrity_app_role_insert")
            append_clinical_event(app_session, event)
            app_session.commit()
            event_id = event.event_id
        finally:
            app_session.close()

        with pytest.raises(DBAPIError) as update_exc:
            with app_engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE clinical_events SET payload = payload "
                        "WHERE event_id = CAST(:event_id AS UUID)"
                    ),
                    {"event_id": str(event_id)},
                )
        assert "permission denied" in str(update_exc.value).lower()

        with pytest.raises(DBAPIError) as delete_exc:
            with app_engine.connect() as conn:
                conn.execute(
                    text(
                        "DELETE FROM clinical_events "
                        "WHERE event_id = CAST(:event_id AS UUID)"
                    ),
                    {"event_id": str(event_id)},
                )
        assert "permission denied" in str(delete_exc.value).lower()

        with pytest.raises(DBAPIError) as state_exc:
            with app_engine.connect() as conn:
                conn.exec_driver_sql(
                    "UPDATE event_chain_state SET last_hash = last_hash"
                )
        assert "permission denied" in str(state_exc.value).lower()

        with app_engine.connect() as conn:
            assert conn.exec_driver_sql(
                "SELECT count(*) FROM clinical_events"
            ).scalar() >= 1
    finally:
        app_engine.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP OWNED BY "{role}"')
            conn.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')

    session = SessionLocal()
    try:
        verification = verify_chain(session)
    finally:
        session.close()
    assert verification.valid is True
    assert verification.events_checked == 1


def test_migration_is_idempotent_on_postgres():
    first = migrate(engine)
    assert first.valid is True
    second = migrate(engine)
    assert second.valid is True


def test_disabled_trigger_fails_readiness():
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE clinical_events "
            "DISABLE TRIGGER trg_clinical_events_no_update"
        )
    try:
        assert integrity_triggers_ready(engine) is False
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "ALTER TABLE clinical_events "
                "ENABLE TRIGGER trg_clinical_events_no_update"
            )
    assert integrity_triggers_ready(engine) is True


def _create_app_role(role, password):
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar()
        if exists:
            conn.exec_driver_sql(f'DROP OWNED BY "{role}"')
            conn.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
    apply_app_role_grants(engine, role, password)


def _drop_app_role(role):
    with engine.begin() as conn:
        conn.exec_driver_sql(f'DROP OWNED BY "{role}"')
        conn.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')


def _require_superuser():
    with engine.connect() as conn:
        is_superuser = conn.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    if not is_superuser:
        pytest.skip("requires a superuser test connection")


def test_integral_large_float_payload_verifies():
    # Regression: json.dumps renders 1e20 as "1e+20" but JSONB returns an
    # integer, so a naive canonical form would make a legitimate event fail
    # verification and halt ingestion for every ward.
    session = SessionLocal()
    try:
        event = _make_event("integrity_large_float")
        event.payload = {
            "vitals": {"temp": 36.6, "spo2": 98.0, "big": 1e20, "tiny": 1e-7},
            "counter": 10**20,
        }
        append_clinical_event(session, event)
        session.commit()
    finally:
        session.close()

    session = SessionLocal()
    try:
        verification = verify_chain(session)
    finally:
        session.close()
    assert verification.valid is True, verification.as_dict()


def test_migration_backfills_legacy_rows_with_append_only_triggers_installed():
    # Simulates a deployment whose rows predate hashing: hashes are cleared
    # under the owner role, then the migration must re-chain them even though
    # the append-only UPDATE trigger is present.
    session = SessionLocal()
    try:
        for index in range(3):
            append_clinical_event(session, _make_event(f"integrity_legacy_{index}"))
            session.commit()
    finally:
        session.close()

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE clinical_events ALTER COLUMN prev_hash DROP NOT NULL"
        )
        conn.exec_driver_sql(
            "ALTER TABLE clinical_events ALTER COLUMN event_hash DROP NOT NULL"
        )
        conn.exec_driver_sql("ALTER TABLE clinical_events DISABLE TRIGGER USER")
        conn.exec_driver_sql(
            "UPDATE clinical_events SET prev_hash = NULL, event_hash = NULL"
        )
        conn.exec_driver_sql("ALTER TABLE clinical_events ENABLE TRIGGER USER")

    result = migrate(engine)
    assert result.valid is True, result.as_dict()
    assert result.events_checked == 3
    assert integrity_triggers_ready(engine) is True


def test_app_role_cannot_alter_guards_or_bypass_triggers():
    _require_superuser()
    role = f"vigil_test_guard_{uuid.uuid4().hex[:8]}"
    password = "test-app-role-password-123456"
    _create_app_role(role, password)
    app_engine = create_engine(engine.url.set(username=role, password=password))
    try:
        attempts = {
            "disable guard trigger": (
                "ALTER TABLE clinical_events "
                "DISABLE TRIGGER trg_clinical_events_no_update"
            ),
            "truncate": "TRUNCATE clinical_events",
            "drop guard trigger": (
                "DROP TRIGGER trg_clinical_events_no_update ON clinical_events"
            ),
            "replace chain head": "DELETE FROM event_chain_state",
            "bypass replication role": "SET session_replication_role = replica",
            "create trigger": (
                "CREATE TRIGGER t_evil BEFORE UPDATE ON clinical_events "
                "FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation()"
            ),
        }
        for label, sql in attempts.items():
            with pytest.raises(DBAPIError, match=r"(?i)permission denied|must be owner|superuser"):
                with app_engine.begin() as conn:
                    conn.exec_driver_sql(sql)
    finally:
        app_engine.dispose()
        _drop_app_role(role)

    assert integrity_triggers_ready(engine) is True
    session = SessionLocal()
    try:
        assert verify_chain(session).valid is True
    finally:
        session.close()


def test_payload_columns_are_jsonb_like_production_schema():
    # init_db.sql creates JSONB. If the ORM mapped a different type, the
    # tests would exercise different number handling than production does.
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'clinical_events' "
                "AND column_name IN ('payload', 'metadata')"
            )
        ).all()
    assert dict(rows) == {"payload": "jsonb", "metadata": "jsonb"}


def test_hash_version_is_stored_and_new_rows_use_current_version():
    session = SessionLocal()
    try:
        append_clinical_event(session, _make_event("integrity_hash_version"))
        session.commit()
    finally:
        session.close()

    with engine.connect() as conn:
        versions = conn.exec_driver_sql(
            "SELECT DISTINCT hash_version FROM clinical_events"
        ).scalars().all()
    assert versions == [2]


def _write_v1_legacy_chain(count):
    """Writes rows exactly as the pre-hash_version build did: canonical v1
    hashes, no version column value other than the legacy default."""
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE clinical_events DISABLE TRIGGER USER")
        session = Session(bind=conn)
        prev = GENESIS_HASH
        last = None
        for index in range(count):
            event = _make_event(f"integrity_v1_legacy_{index}")
            event.ingested_at = datetime.datetime.now(datetime.timezone.utc)
            event.prev_hash = prev
            event.event_hash = compute_event_hash(event, prev, 1)
            event.hash_version = 1
            session.add(event)
            session.flush()
            prev = event.event_hash
            last = event
        state = session.get(EventChainStateModel, CHAIN_ID)
        state.last_event_id = last.id
        state.last_hash = prev
        session.flush()
        conn.exec_driver_sql("ALTER TABLE clinical_events ENABLE TRIGGER USER")


def test_legacy_v1_history_survives_migration_and_extends_under_v2():
    _write_v1_legacy_chain(3)
    session = SessionLocal()
    try:
        before = verify_chain(session)
    finally:
        session.close()
    assert before.valid is True, before.as_dict()

    # Simulate a database created before the hash_version column existed.
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE clinical_events DROP COLUMN hash_version")

    result = migrate(engine)
    assert result.valid is True, result.as_dict()
    assert result.events_checked == 3

    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT DISTINCT hash_version FROM clinical_events"
        ).scalars().all() == [1]

    session = SessionLocal()
    try:
        append_clinical_event(session, _make_event("integrity_after_v1_migration"))
        session.commit()
        after = verify_chain(session)
    finally:
        session.close()
    assert after.valid is True, after.as_dict()
    assert after.events_checked == 4


def test_v1_row_with_tampered_payload_is_still_detected():
    _write_v1_legacy_chain(2)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE clinical_events DISABLE TRIGGER USER")
        conn.exec_driver_sql(
            "UPDATE clinical_events SET payload = '{\"vitals\": {\"hr\": 999}}'::jsonb "
            "WHERE id = (SELECT min(id) FROM clinical_events)"
        )
        conn.exec_driver_sql("ALTER TABLE clinical_events ENABLE TRIGGER USER")

    session = SessionLocal()
    try:
        result = verify_chain(session)
    finally:
        session.close()
    assert result.valid is False
    assert result.reason == "event_hash_mismatch"
    assert result.first_invalid_position == 1


def test_unsupported_hash_version_is_rejected_by_verifier():
    _write_v1_legacy_chain(1)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE clinical_events DISABLE TRIGGER USER")
        conn.exec_driver_sql("UPDATE clinical_events SET hash_version = 9")
        conn.exec_driver_sql("ALTER TABLE clinical_events ENABLE TRIGGER USER")

    session = SessionLocal()
    try:
        result = verify_chain(session)
    finally:
        session.close()
    assert result.valid is False
    assert result.reason == "unsupported_hash_version"


def test_ensure_chain_state_refuses_to_genesis_over_existing_rows():
    session = SessionLocal()
    try:
        append_clinical_event(session, _make_event("integrity_orphan_guard"))
        session.commit()
        session.execute(text("DELETE FROM event_chain_state"))
        session.commit()
        with pytest.raises(ChainIntegrityError) as exc:
            ensure_chain_state(session)
        session.rollback()
        assert "migrate_integrity" in str(exc.value)
    finally:
        session.close()


def test_concurrent_writers_never_produce_false_verification_failures():
    # Regression: verify_chain reads the event list and the chain head in two
    # statements. Without the verification lock, an append committing between
    # them looked like a head mismatch and halted ingestion.
    writers = 3
    per_writer = 10
    stop = threading.Event()
    failures = []

    def writer(index):
        for item in range(per_writer):
            session = SessionLocal()
            try:
                append_clinical_event(session, _make_event(f"integrity_race_{index}_{item}"))
                session.commit()
            except Exception as exc:  # pragma: no cover - surfaced below
                session.rollback()
                failures.append(exc)
            finally:
                session.close()

    def verifier():
        while not stop.is_set():
            session = SessionLocal()
            try:
                result = verify_chain(session)
                if not result.valid:
                    failures.append(result.as_dict())
            finally:
                session.close()

    verify_thread = threading.Thread(target=verifier)
    writer_threads = [threading.Thread(target=writer, args=(i,)) for i in range(writers)]
    verify_thread.start()
    for thread in writer_threads:
        thread.start()
    for thread in writer_threads:
        thread.join(timeout=120)
    stop.set()
    verify_thread.join(timeout=120)

    assert not failures, failures[:3]
    session = SessionLocal()
    try:
        final = verify_chain(session)
    finally:
        session.close()
    assert final.valid is True
    assert final.events_checked == writers * per_writer
