import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.config.settings import settings
from backend.event_store.database import Base
from backend.event_store.integrity import (
    CHAIN_ID,
    GENESIS_HASH,
    SUPPORTED_HASH_VERSIONS,
    _sqlite_trigger_sql,
    assert_integrity_ready,
    compute_event_hash,
    install_integrity_triggers,
    verify_chain,
)
from backend.event_store.models import (
    CANONICAL_HASH_VERSION,
    ClinicalEventModel,
    EventChainStateModel,
)

ROLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Rows that predate hash_version were hashed by the original canonical form.
LEGACY_HASH_VERSION = 1
UPDATE_GUARD_TRIGGER = "trg_clinical_events_no_update"


def _database_url() -> str:
    return (
        os.getenv("MIGRATION_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
        or settings.DATABASE_URL
    )


def _add_missing_columns(engine) -> None:
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("clinical_events")}
    additions = {
        "prev_hash": "VARCHAR(64)",
        "event_hash": "VARCHAR(64)",
        "corrects_event_id": "UUID" if engine.dialect.name == "postgresql" else "CHAR(32)",
        "correction_reason": "TEXT",
    }
    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE clinical_events ADD COLUMN {name} {sql_type}"
                )

        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                         WHERE conname = 'fk_clinical_events_corrects_event_id'
                    ) THEN
                        ALTER TABLE clinical_events
                        ADD CONSTRAINT fk_clinical_events_corrects_event_id
                        FOREIGN KEY (corrects_event_id)
                        REFERENCES clinical_events(event_id);
                    END IF;
                END;
                $$;
                """
            )


def _add_hash_version_column(engine) -> None:
    # Existing rows are hashed by the original canonical form, so they are
    # tagged version 1. New rows default to the current version.
    existing = {column["name"] for column in inspect(engine).get_columns("clinical_events")}
    if "hash_version" in existing:
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE clinical_events ADD COLUMN hash_version INTEGER "
            f"NOT NULL DEFAULT {LEGACY_HASH_VERSION}"
        )
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql(
                "ALTER TABLE clinical_events ALTER COLUMN hash_version "
                f"SET DEFAULT {CANONICAL_HASH_VERSION}"
            )


def _backfill_chain(session: Session) -> str:
    events = (
        session.execute(select(ClinicalEventModel).order_by(ClinicalEventModel.id))
        .scalars()
        .yield_per(1000)
    )
    last_hash = GENESIS_HASH
    seen_unhashed = False

    for event in events:
        has_prev = bool(event.prev_hash)
        has_hash = bool(event.event_hash)
        if has_prev != has_hash:
            raise RuntimeError(
                f"Event id={event.id} has only one of prev_hash/event_hash; "
                "refusing to repair ambiguous history"
            )

        if has_prev:
            if seen_unhashed:
                raise RuntimeError(
                    f"Event id={event.id} is hashed but follows unhashed events; "
                    "refusing to reorder or rehash history"
                )
            if event.prev_hash != last_hash:
                raise RuntimeError(
                    f"Existing chain link mismatch at event id={event.id}; "
                    "refusing to modify history"
                )
            if event.hash_version not in SUPPORTED_HASH_VERSIONS:
                raise RuntimeError(
                    f"Event id={event.id} has unsupported hash_version "
                    f"{event.hash_version}; refusing to modify history"
                )
            calculated = compute_event_hash(event, event.prev_hash, event.hash_version)
            if calculated != event.event_hash:
                raise RuntimeError(
                    f"Existing event hash mismatch at event id={event.id}; "
                    "refusing to modify history"
                )
            last_hash = event.event_hash
            continue

        seen_unhashed = True
        if event.device_timestamp is None or event.ingested_at is None:
            raise RuntimeError(
                f"Event id={event.id} is missing timestamps required for hashing"
            )
        # Rows that never had a hash have no prior history to preserve, so
        # they are hashed with the current canonical form.
        event.hash_version = CANONICAL_HASH_VERSION
        event.prev_hash = last_hash
        event.event_hash = compute_event_hash(event, last_hash, CANONICAL_HASH_VERSION)
        last_hash = event.event_hash

    session.flush()
    return last_hash


def _suspend_update_guard(conn) -> None:
    # The backfill must UPDATE rows that have no hashes yet. The UPDATE guard
    # is disabled only inside the migration transaction and restored before it
    # commits, so a failed backfill rolls the guard back as well.
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql(
            f"ALTER TABLE clinical_events DISABLE TRIGGER {UPDATE_GUARD_TRIGGER}"
        )
    else:
        conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {UPDATE_GUARD_TRIGGER}")


def _restore_update_guard(conn) -> None:
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql(
            f"ALTER TABLE clinical_events ENABLE TRIGGER {UPDATE_GUARD_TRIGGER}"
        )
    else:
        statement = next(
            sql for sql in _sqlite_trigger_sql() if UPDATE_GUARD_TRIGGER in sql
        )
        conn.exec_driver_sql(statement)


def _backfill_under_guard(engine) -> str:
    with engine.begin() as conn:
        _suspend_update_guard(conn)
        session = Session(bind=conn, autoflush=False)
        last_hash = _backfill_chain(session)
        _set_chain_state(session, last_hash)
        session.flush()
        _restore_update_guard(conn)
    return last_hash


def _set_chain_state(session: Session, last_hash: str) -> None:
    last_event = session.execute(
        select(ClinicalEventModel).order_by(ClinicalEventModel.id.desc()).limit(1)
    ).scalar_one_or_none()
    state = session.get(EventChainStateModel, CHAIN_ID)
    if state is None:
        state = EventChainStateModel(
            chain_id=CHAIN_ID,
            last_event_id=last_event.id if last_event else None,
            last_hash=last_hash,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(state)
    else:
        state.last_event_id = last_event.id if last_event else None
        state.last_hash = last_hash
        state.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()


def _enforce_not_null(engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE clinical_events ALTER COLUMN prev_hash SET NOT NULL"
        )
        conn.exec_driver_sql(
            "ALTER TABLE clinical_events ALTER COLUMN event_hash SET NOT NULL"
        )


def _create_indexes(engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_events_prev_hash "
            "ON clinical_events (prev_hash)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_clinical_events_event_hash "
            "ON clinical_events (event_hash)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_clinical_events_corrects_event_id "
            "ON clinical_events (corrects_event_id)"
        )


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def apply_app_role_grants(engine, role: str, password: str) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Application-role provisioning is PostgreSQL-only")
    if not ROLE_NAME_PATTERN.match(role):
        raise ValueError(f"Invalid PostgreSQL role name: {role!r}")
    if len(password) < 16:
        raise ValueError("Application role password must be at least 16 characters")

    role_literal = _quote_literal(role)
    password_literal = _quote_literal(password)
    role_identifier = _quote_identifier(role)

    create_role_sql = (
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN "
        f"EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', {role_literal}, {password_literal}); "
        "ELSE "
        f"EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', {role_literal}, {password_literal}); "
        "END IF; END $$;"
    )

    with engine.begin() as conn:
        conn.exec_driver_sql(create_role_sql.replace("%", "%%"))
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {role_identifier}")
        conn.exec_driver_sql(
            f"REVOKE ALL ON clinical_events FROM {role_identifier}"
        )
        conn.exec_driver_sql(
            f"GRANT SELECT, INSERT ON clinical_events TO {role_identifier}"
        )
        conn.exec_driver_sql(
            f"REVOKE UPDATE, DELETE, TRUNCATE ON clinical_events FROM {role_identifier}"
        )
        conn.exec_driver_sql(
            f"REVOKE ALL ON event_chain_state FROM {role_identifier}"
        )
        conn.exec_driver_sql(
            f"GRANT SELECT ON event_chain_state TO {role_identifier}"
        )
        for table in ("agent_audit_logs", "chain_verification_logs"):
            conn.exec_driver_sql(f"REVOKE ALL ON {table} FROM {role_identifier}")
            conn.exec_driver_sql(
                f"GRANT SELECT, INSERT ON {table} TO {role_identifier}"
            )
            conn.exec_driver_sql(
                f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM {role_identifier}"
            )
        for table in ("wards", "staff", "patients"):
            conn.exec_driver_sql(f"REVOKE ALL ON {table} FROM {role_identifier}")
            conn.exec_driver_sql(
                f"GRANT SELECT, INSERT ON {table} TO {role_identifier}"
            )
        conn.exec_driver_sql(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role_identifier}"
        )
        conn.exec_driver_sql(
            f"GRANT EXECUTE ON FUNCTION vigil_validate_chain_link() TO {role_identifier}"
        )
        conn.exec_driver_sql(
            f"GRANT EXECUTE ON FUNCTION vigil_update_chain_head() TO {role_identifier}"
        )
        conn.exec_driver_sql(
            f"GRANT EXECUTE ON FUNCTION vigil_block_append_only_mutation() TO {role_identifier}"
        )


def migrate(engine, app_role: str = "", app_password: str = ""):
    if not inspect(engine).has_table("clinical_events"):
        raise RuntimeError(
            "clinical_events table not found; initialize the database before migrating"
        )

    Base.metadata.create_all(bind=engine)
    _add_missing_columns(engine)
    _add_hash_version_column(engine)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _backfill_under_guard(engine)

    _create_indexes(engine)
    _enforce_not_null(engine)
    install_integrity_triggers(engine)

    if app_role:
        if not app_password:
            raise RuntimeError(
                "VIGIL_APP_DB_PASSWORD is required to provision the application role"
            )
        apply_app_role_grants(engine, app_role, app_password)

    assert_integrity_ready(engine)
    verify_session = session_factory()
    try:
        result = verify_chain(verify_session)
    finally:
        verify_session.close()
    if not result.valid:
        raise RuntimeError(
            f"Integrity verification failed after migration: {result.reason}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply Vigil append-only/hash-chain schema and permissions."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify schema, triggers, and the existing chain without changing it.",
    )
    parser.add_argument(
        "--create-app-role",
        action="store_true",
        help="Provision/update the PostgreSQL application role from env settings.",
    )
    args = parser.parse_args()

    url = _database_url()
    engine = create_engine(url, pool_pre_ping=True)

    if args.check:
        assert_integrity_ready(engine)
        session = Session(bind=engine)
        try:
            result = verify_chain(session)
        finally:
            session.close()
        print(json.dumps(result.as_dict(), indent=2))
        return 0 if result.valid else 1

    role = os.getenv("VIGIL_APP_DB_ROLE", "vigil_app").strip() or "vigil_app"
    password = os.getenv("VIGIL_APP_DB_PASSWORD", "")
    if args.create_app_role and not password:
        print(
            "VIGIL_APP_DB_PASSWORD must be set when --create-app-role is used",
            file=sys.stderr,
        )
        return 2

    result = migrate(
        engine,
        app_role=role if args.create_app_role else "",
        app_password=password if args.create_app_role else "",
    )
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
