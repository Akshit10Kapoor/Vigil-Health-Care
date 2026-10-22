import dataclasses
import datetime
import decimal
import hashlib
import json
import math
import threading
import uuid
from typing import Any, Optional

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.event_store.models import (
    CANONICAL_HASH_VERSION,
    ChainVerificationLogModel,
    ClinicalEventModel,
    EventChainStateModel,
)

GENESIS_HASH = "0" * 64
CHAIN_ID = "clinical_events"
VERIFIER_VERSION = "vigil-integrity-v2"
SUPPORTED_HASH_VERSIONS = (1, 2)
# Single advisory-lock key that serializes every chain append and every full
# verification pass. See append_clinical_event and verify_chain.
CHAIN_LOCK_ID = 0x564947494C

CLINICAL_TRIGGER_NAMES = (
    "trg_clinical_events_chain_link",
    "trg_clinical_events_chain_head",
    "trg_clinical_events_no_update",
    "trg_clinical_events_no_delete",
    "trg_clinical_events_no_truncate",
)
AUDIT_TRIGGER_NAMES = (
    "trg_agent_audit_logs_no_update",
    "trg_agent_audit_logs_no_delete",
    "trg_agent_audit_logs_no_truncate",
)
VERIFICATION_TRIGGER_NAMES = (
    "trg_chain_verification_logs_no_update",
    "trg_chain_verification_logs_no_delete",
    "trg_chain_verification_logs_no_truncate",
)
EXPECTED_TRIGGERS = {
    "clinical_events": CLINICAL_TRIGGER_NAMES,
    "agent_audit_logs": AUDIT_TRIGGER_NAMES,
    "chain_verification_logs": VERIFICATION_TRIGGER_NAMES,
}


class ChainIntegrityError(RuntimeError):
    pass


_integrity_failure_lock = threading.Lock()
_integrity_failure_reason: Optional[str] = None


def mark_integrity_failure(reason: str) -> None:
    global _integrity_failure_reason
    with _integrity_failure_lock:
        _integrity_failure_reason = reason


def clear_integrity_failure() -> None:
    global _integrity_failure_reason
    with _integrity_failure_lock:
        _integrity_failure_reason = None


def get_integrity_failure() -> Optional[str]:
    with _integrity_failure_lock:
        return _integrity_failure_reason


def assert_integrity_healthy() -> None:
    reason = get_integrity_failure()
    if reason:
        raise ChainIntegrityError(
            "Clinical event ingestion is halted because the integrity check "
            f"failed: {reason}"
        )


@dataclasses.dataclass(frozen=True)
class ChainVerificationResult:
    valid: bool
    events_checked: int
    checked_at: datetime.datetime
    head_hash: str
    reason: Optional[str] = None
    first_invalid_event_id: Optional[uuid.UUID] = None
    first_invalid_position: Optional[int] = None
    verifier_version: str = VERIFIER_VERSION

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "events_checked": self.events_checked,
            "checked_at": self.checked_at.isoformat(),
            "head_hash": self.head_hash,
            "reason": self.reason,
            "first_invalid_event_id": (
                str(self.first_invalid_event_id) if self.first_invalid_event_id else None
            ),
            "first_invalid_position": self.first_invalid_position,
            "verifier_version": self.verifier_version,
        }


def _utc_iso(value: Optional[datetime.datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return _utc_iso(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _canonical_json_v1(value: Any) -> str:
    # Hash version 1, used by rows written before hash_version existed. Do not
    # change: altering this output would invalidate stored history.
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _canonical_number_v2(value: Any) -> str:
    # PostgreSQL JSONB returns integral numbers as integers and non-integral
    # numbers as floats, so the same logical value must render identically
    # before and after a round-trip. Integral values (including 98.0 and 1e20)
    # render as integers; everything else as a plain decimal with no exponent.
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("non-finite numbers cannot be hashed")
    if value.is_integer():
        return str(int(value))
    return format(decimal.Decimal(repr(value)).normalize(), "f")


def _canonical_value_v2(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _canonical_number_v2(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        items = sorted(((str(key), item) for key, item in value.items()), key=lambda kv: kv[0])
        return "{" + ",".join(
            json.dumps(key, ensure_ascii=False) + ":" + _canonical_value_v2(item)
            for key, item in items
        ) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical_value_v2(item) for item in value) + "]"
    return json.dumps(_json_default(value), ensure_ascii=False)


def _canonical_uuid(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError):
        return str(value)


def canonical_event_dict(event: ClinicalEventModel) -> dict:
    return {
        "event_id": _canonical_uuid(event.event_id),
        "event_type": event.event_type,
        "patient_id": event.patient_id,
        "ward_id": event.ward_id,
        "bed_number": event.bed_number,
        "staff_id": event.staff_id,
        "device_timestamp": _utc_iso(event.device_timestamp),
        "device_tz_offset": event.device_tz_offset,
        "ingested_at": _utc_iso(event.ingested_at),
        "payload": event.payload if event.payload is not None else {},
        "raw_note": event.raw_note,
        "client_sync_id": event.client_sync_id,
        "metadata": event.metadata_info,
        "corrects_event_id": _canonical_uuid(event.corrects_event_id),
        "correction_reason": event.correction_reason,
    }


def compute_event_hash(
    event: ClinicalEventModel,
    prev_hash: str,
    version: int = CANONICAL_HASH_VERSION,
) -> str:
    if version == 1:
        digest_input = _canonical_json_v1(
            {"prev_hash": prev_hash, "event": canonical_event_dict(event)}
        )
    elif version == 2:
        digest_input = _canonical_value_v2(
            {
                "hash_version": 2,
                "prev_hash": prev_hash,
                "event": canonical_event_dict(event),
            }
        )
    else:
        raise ValueError(f"unsupported hash version: {version}")
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def _acquire_chain_lock(db: Session) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CHAIN_LOCK_ID})


def get_chain_state(db: Session) -> EventChainStateModel:
    # populate_existing forces a reload so a cached head from earlier in the
    # same session cannot be used after another transaction advanced the chain.
    state = db.get(EventChainStateModel, CHAIN_ID, populate_existing=True)
    if state is None:
        raise ChainIntegrityError(
            "clinical event chain state is missing; run the integrity migration"
        )
    if not state.last_hash or len(state.last_hash) != 64:
        raise ChainIntegrityError("clinical event chain state has an invalid head hash")
    return state


def ensure_chain_state(db: Session, commit: bool = True) -> EventChainStateModel:
    state = db.get(EventChainStateModel, CHAIN_ID)
    if state is None:
        # A GENESIS head over existing rows would make them look like a fork
        # rather than legacy history. Only the migration may backfill them.
        has_events = db.execute(select(ClinicalEventModel.id).limit(1)).first()
        if has_events is not None:
            raise ChainIntegrityError(
                "clinical_events already contains rows but no chain state exists; "
                "run backend/scripts/migrate_integrity.py"
            )
        state = EventChainStateModel(
            chain_id=CHAIN_ID,
            last_event_id=None,
            last_hash=GENESIS_HASH,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(state)
        db.flush()
        if commit:
            db.commit()
    return state


def _column_default(model, column_name: str):
    default = model.__table__.c[column_name].default
    if default is None or not hasattr(default, "arg"):
        raise ChainIntegrityError(f"{column_name} has no scalar default to hash")
    return default.arg


def _validate_correction(db: Session, event: ClinicalEventModel) -> None:
    if event.event_type == "clinical_event_correction":
        if not event.corrects_event_id:
            raise ValueError("A correction event must set corrects_event_id")
        if not event.correction_reason or not event.correction_reason.strip():
            raise ValueError("A correction event must include a correction_reason")
        target = (
            db.query(ClinicalEventModel)
            .filter(ClinicalEventModel.event_id == event.corrects_event_id)
            .first()
        )
        if target is None:
            raise ValueError(
                f"Correction target '{event.corrects_event_id}' was not found"
            )
    elif event.corrects_event_id or event.correction_reason:
        raise ValueError(
            "corrects_event_id and correction_reason are only valid for "
            "clinical_event_correction events"
        )


def append_clinical_event(db: Session, event: ClinicalEventModel) -> ClinicalEventModel:
    assert_integrity_healthy()
    _validate_correction(db, event)
    if event.event_id is None:
        event.event_id = uuid.uuid4()
    if event.ingested_at is None:
        event.ingested_at = datetime.datetime.now(datetime.timezone.utc)
    if event.device_tz_offset is None:
        # Column defaults are applied at INSERT time, after the hash is computed.
        # Apply them here so the hashed value is the value that gets stored.
        event.device_tz_offset = _column_default(ClinicalEventModel, "device_tz_offset")

    # The lock is held until the caller commits, so the INSERT below receives
    # the next id and the next prev_hash with no concurrent writer in between.
    _acquire_chain_lock(db)
    state = get_chain_state(db)
    event.hash_version = CANONICAL_HASH_VERSION
    event.prev_hash = state.last_hash
    event.event_hash = compute_event_hash(event, state.last_hash, CANONICAL_HASH_VERSION)

    db.add(event)
    db.flush()
    db.refresh(state)
    if state.last_hash != event.event_hash:
        raise ChainIntegrityError(
            "database chain-head trigger did not advance; integrity triggers are not installed"
        )
    return event


def _acquire_verification_lock(db: Session) -> bool:
    # Session-level (not transaction-level) lock: a read-only verification
    # must not keep appends blocked until the caller happens to commit.
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return False
    db.execute(text("SELECT pg_advisory_lock(:key)"), {"key": CHAIN_LOCK_ID})
    return True


def _release_verification_lock(db: Session) -> None:
    db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": CHAIN_LOCK_ID})


def verify_chain(db: Session) -> ChainVerificationResult:
    # Verification reads the event list and the head in separate statements.
    # Holding the same lock as appends guarantees both reads see one chain
    # state; otherwise a concurrent commit could look like head tampering.
    locked = _acquire_verification_lock(db)
    try:
        return _verify_chain_unlocked(db)
    finally:
        if locked:
            _release_verification_lock(db)


def _verify_chain_unlocked(db: Session) -> ChainVerificationResult:
    checked_at = datetime.datetime.now(datetime.timezone.utc)
    expected_prev = GENESIS_HASH
    last_event_id = None
    events_checked = 0

    events = (
        db.execute(select(ClinicalEventModel).order_by(ClinicalEventModel.id))
        .scalars()
        .yield_per(1000)
    )

    for event in events:
        events_checked += 1
        last_event_id = event.id
        if not event.prev_hash or len(event.prev_hash) != 64:
            return ChainVerificationResult(
                valid=False,
                events_checked=events_checked,
                checked_at=checked_at,
                head_hash=expected_prev,
                reason="missing_or_invalid_prev_hash",
                first_invalid_event_id=event.event_id,
                first_invalid_position=events_checked,
            )
        if not event.event_hash or len(event.event_hash) != 64:
            return ChainVerificationResult(
                valid=False,
                events_checked=events_checked,
                checked_at=checked_at,
                head_hash=expected_prev,
                reason="missing_or_invalid_event_hash",
                first_invalid_event_id=event.event_id,
                first_invalid_position=events_checked,
            )
        if event.prev_hash != expected_prev:
            return ChainVerificationResult(
                valid=False,
                events_checked=events_checked,
                checked_at=checked_at,
                head_hash=expected_prev,
                reason="prev_hash_mismatch",
                first_invalid_event_id=event.event_id,
                first_invalid_position=events_checked,
            )
        if event.hash_version not in SUPPORTED_HASH_VERSIONS:
            return ChainVerificationResult(
                valid=False,
                events_checked=events_checked,
                checked_at=checked_at,
                head_hash=expected_prev,
                reason="unsupported_hash_version",
                first_invalid_event_id=event.event_id,
                first_invalid_position=events_checked,
            )
        calculated = compute_event_hash(event, event.prev_hash, event.hash_version)
        if calculated != event.event_hash:
            return ChainVerificationResult(
                valid=False,
                events_checked=events_checked,
                checked_at=checked_at,
                head_hash=expected_prev,
                reason="event_hash_mismatch",
                first_invalid_event_id=event.event_id,
                first_invalid_position=events_checked,
            )
        expected_prev = event.event_hash

    state = db.get(EventChainStateModel, CHAIN_ID)
    if state is None:
        return ChainVerificationResult(
            valid=False,
            events_checked=events_checked,
            checked_at=checked_at,
            head_hash=expected_prev,
            reason="chain_state_missing",
        )

    if events_checked == 0:
        if state.last_event_id is not None or state.last_hash != GENESIS_HASH:
            return ChainVerificationResult(
                valid=False,
                events_checked=0,
                checked_at=checked_at,
                head_hash=state.last_hash,
                reason="chain_head_mismatch",
            )
    elif state.last_event_id != last_event_id or state.last_hash != expected_prev:
        return ChainVerificationResult(
            valid=False,
            events_checked=events_checked,
            checked_at=checked_at,
            head_hash=state.last_hash,
            reason="chain_head_mismatch",
            first_invalid_position=events_checked,
        )

    return ChainVerificationResult(
        valid=True,
        events_checked=events_checked,
        checked_at=checked_at,
        head_hash=expected_prev,
    )


def record_verification(
    db: Session, result: ChainVerificationResult, commit: bool = True
) -> ChainVerificationLogModel:
    log = ChainVerificationLogModel(
        chain_id=CHAIN_ID,
        checked_at=result.checked_at,
        valid=result.valid,
        events_checked=result.events_checked,
        first_invalid_event_id=result.first_invalid_event_id,
        first_invalid_position=result.first_invalid_position,
        head_hash=result.head_hash,
        reason=result.reason,
        verifier_version=result.verifier_version,
    )
    db.add(log)
    if commit:
        db.commit()
    return log


def integrity_schema_ready(engine: Engine) -> bool:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "event_chain_state" not in tables or "chain_verification_logs" not in tables:
        return False
    columns = {column["name"] for column in inspector.get_columns("clinical_events")}
    return {
        "prev_hash",
        "event_hash",
        "hash_version",
        "corrects_event_id",
        "correction_reason",
    } <= columns


def integrity_triggers_ready(engine: Engine) -> bool:
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            found = {
                (row[0], row[1])
                for row in conn.execute(
                    text(
                        "SELECT c.relname, t.tgname "
                        "FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid = t.tgrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE NOT t.tgisinternal "
                        "AND n.nspname = ANY (current_schemas(false)) "
                        "AND t.tgenabled <> 'D'"
                    )
                )
            }
        elif engine.dialect.name == "sqlite":
            found = {
                (row[0], row[1])
                for row in conn.execute(
                    text(
                        "SELECT tbl_name, name FROM sqlite_master "
                        "WHERE type = 'trigger'"
                    )
                )
            }
        else:
            return False

    for table, names in EXPECTED_TRIGGERS.items():
        for name in names:
            if engine.dialect.name == "sqlite" and name.endswith("_no_truncate"):
                continue
            if (table, name) not in found:
                return False
    return True


def assert_integrity_ready(engine: Engine) -> None:
    if not integrity_schema_ready(engine):
        raise RuntimeError(
            "Clinical event integrity schema is missing. Run "
            "`python -m backend.scripts.migrate_integrity` before starting the API."
        )
    if not integrity_triggers_ready(engine):
        raise RuntimeError(
            "Clinical event integrity triggers are missing. Run "
            "`python -m backend.scripts.migrate_integrity` before starting the API."
        )
    with engine.connect() as conn:
        state = conn.execute(
            text(
                "SELECT last_hash FROM event_chain_state WHERE chain_id = :chain_id"
            ),
            {"chain_id": CHAIN_ID},
        ).first()
    if state is None or not state[0] or len(state[0]) != 64:
        raise RuntimeError(
            "Clinical event chain state is missing. Run "
            "`python -m backend.scripts.migrate_integrity` before starting the API."
        )


def _postgres_trigger_sql() -> list[str]:
    return [
        """
        CREATE OR REPLACE FUNCTION vigil_validate_chain_link()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            expected_hash CHAR(64);
        BEGIN
            SELECT last_hash INTO expected_hash
              FROM event_chain_state
             WHERE chain_id = 'clinical_events'
             FOR UPDATE;
            IF expected_hash IS NULL THEN
                RAISE EXCEPTION 'clinical event chain state is missing';
            END IF;
            IF NEW.prev_hash IS DISTINCT FROM expected_hash::text THEN
                RAISE EXCEPTION 'prev_hash does not match the current chain head'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """,
        """
        CREATE OR REPLACE FUNCTION vigil_update_chain_head()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            UPDATE event_chain_state
               SET last_event_id = NEW.id,
                   last_hash = NEW.event_hash,
                   updated_at = CURRENT_TIMESTAMP
             WHERE chain_id = 'clinical_events';
            RETURN NEW;
        END;
        $$;
        """,
        """
        CREATE OR REPLACE FUNCTION vigil_block_append_only_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION USING
                MESSAGE = TG_TABLE_NAME || ' is append-only; ' || TG_OP || ' is not permitted',
                ERRCODE = '42501';
        END;
        $$;
        """,
        "DROP TRIGGER IF EXISTS trg_clinical_events_chain_link ON clinical_events;",
        """
        CREATE TRIGGER trg_clinical_events_chain_link
        BEFORE INSERT ON clinical_events
        FOR EACH ROW EXECUTE FUNCTION vigil_validate_chain_link();
        """,
        "DROP TRIGGER IF EXISTS trg_clinical_events_chain_head ON clinical_events;",
        """
        CREATE TRIGGER trg_clinical_events_chain_head
        AFTER INSERT ON clinical_events
        FOR EACH ROW EXECUTE FUNCTION vigil_update_chain_head();
        """,
        "DROP TRIGGER IF EXISTS trg_clinical_events_no_update ON clinical_events;",
        """
        CREATE TRIGGER trg_clinical_events_no_update
        BEFORE UPDATE ON clinical_events
        FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_clinical_events_no_delete ON clinical_events;",
        """
        CREATE TRIGGER trg_clinical_events_no_delete
        BEFORE DELETE ON clinical_events
        FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_clinical_events_no_truncate ON clinical_events;",
        """
        CREATE TRIGGER trg_clinical_events_no_truncate
        BEFORE TRUNCATE ON clinical_events
        FOR EACH STATEMENT EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_agent_audit_logs_no_update ON agent_audit_logs;",
        """
        CREATE TRIGGER trg_agent_audit_logs_no_update
        BEFORE UPDATE ON agent_audit_logs
        FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_agent_audit_logs_no_delete ON agent_audit_logs;",
        """
        CREATE TRIGGER trg_agent_audit_logs_no_delete
        BEFORE DELETE ON agent_audit_logs
        FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_agent_audit_logs_no_truncate ON agent_audit_logs;",
        """
        CREATE TRIGGER trg_agent_audit_logs_no_truncate
        BEFORE TRUNCATE ON agent_audit_logs
        FOR EACH STATEMENT EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_chain_verification_logs_no_update ON chain_verification_logs;",
        """
        CREATE TRIGGER trg_chain_verification_logs_no_update
        BEFORE UPDATE ON chain_verification_logs
        FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_chain_verification_logs_no_delete ON chain_verification_logs;",
        """
        CREATE TRIGGER trg_chain_verification_logs_no_delete
        BEFORE DELETE ON chain_verification_logs
        FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
        "DROP TRIGGER IF EXISTS trg_chain_verification_logs_no_truncate ON chain_verification_logs;",
        """
        CREATE TRIGGER trg_chain_verification_logs_no_truncate
        BEFORE TRUNCATE ON chain_verification_logs
        FOR EACH STATEMENT EXECUTE FUNCTION vigil_block_append_only_mutation();
        """,
    ]


def _sqlite_trigger_sql() -> list[str]:
    return [
        """
        CREATE TRIGGER IF NOT EXISTS trg_clinical_events_chain_link
        BEFORE INSERT ON clinical_events
        BEGIN
            SELECT CASE
                WHEN (SELECT last_hash FROM event_chain_state WHERE chain_id = 'clinical_events') IS NULL
                    THEN RAISE(ABORT, 'clinical event chain state is missing')
                WHEN NEW.prev_hash <> (SELECT last_hash FROM event_chain_state WHERE chain_id = 'clinical_events')
                    THEN RAISE(ABORT, 'prev_hash does not match the current chain head')
            END;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_clinical_events_chain_head
        AFTER INSERT ON clinical_events
        BEGIN
            UPDATE event_chain_state
               SET last_event_id = NEW.id,
                   last_hash = NEW.event_hash,
                   updated_at = CURRENT_TIMESTAMP
             WHERE chain_id = 'clinical_events';
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_clinical_events_no_update
        BEFORE UPDATE ON clinical_events
        BEGIN
            SELECT RAISE(ABORT, 'clinical_events is append-only; UPDATE is not permitted');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_clinical_events_no_delete
        BEFORE DELETE ON clinical_events
        BEGIN
            SELECT RAISE(ABORT, 'clinical_events is append-only; DELETE is not permitted');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_agent_audit_logs_no_update
        BEFORE UPDATE ON agent_audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'agent_audit_logs is append-only; UPDATE is not permitted');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_agent_audit_logs_no_delete
        BEFORE DELETE ON agent_audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'agent_audit_logs is append-only; DELETE is not permitted');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_chain_verification_logs_no_update
        BEFORE UPDATE ON chain_verification_logs
        BEGIN
            SELECT RAISE(ABORT, 'chain_verification_logs is append-only; UPDATE is not permitted');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_chain_verification_logs_no_delete
        BEFORE DELETE ON chain_verification_logs
        BEGIN
            SELECT RAISE(ABORT, 'chain_verification_logs is append-only; DELETE is not permitted');
        END;
        """,
    ]


def install_integrity_triggers(engine: Engine) -> None:
    statements = (
        _postgres_trigger_sql()
        if engine.dialect.name == "postgresql"
        else _sqlite_trigger_sql()
        if engine.dialect.name == "sqlite"
        else None
    )
    if statements is None:
        raise RuntimeError(f"Unsupported database dialect: {engine.dialect.name}")
    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)
