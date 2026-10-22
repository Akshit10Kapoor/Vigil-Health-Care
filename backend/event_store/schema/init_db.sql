-- Init SQL Schema for Vigil Append-Only Clinical Event Verification System

CREATE TABLE IF NOT EXISTS wards (
    id SERIAL PRIMARY KEY,
    ward_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    acuity_level VARCHAR(32) NOT NULL DEFAULT 'medium',
    capacity INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff (
    id SERIAL PRIMARY KEY,
    staff_id VARCHAR(64) UNIQUE NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL,
    hashed_password VARCHAR(256) NOT NULL,
    assigned_ward_id VARCHAR(64) REFERENCES wards(ward_id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(64) UNIQUE NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    age INTEGER,
    gender VARCHAR(16),
    bed_number VARCHAR(32) NOT NULL,
    ward_id VARCHAR(64) NOT NULL REFERENCES wards(ward_id),
    admission_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acuity_level VARCHAR(32) DEFAULT 'medium',
    status VARCHAR(32) DEFAULT 'admitted',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clinical_events (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID UNIQUE NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    patient_id VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    ward_id VARCHAR(64) NOT NULL REFERENCES wards(ward_id),
    bed_number VARCHAR(32),
    staff_id VARCHAR(64) NOT NULL REFERENCES staff(staff_id),
    device_timestamp TIMESTAMPTZ NOT NULL,
    device_tz_offset VARCHAR(16) NOT NULL DEFAULT '+05:30',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL,
    raw_note TEXT,
    client_sync_id VARCHAR(128) UNIQUE NOT NULL,
    metadata JSONB,
    prev_hash VARCHAR(64) NOT NULL,
    event_hash VARCHAR(64) NOT NULL,
    hash_version INTEGER NOT NULL DEFAULT 2,
    corrects_event_id UUID REFERENCES clinical_events(event_id),
    correction_reason TEXT,
    CONSTRAINT uq_clinical_events_prev_hash UNIQUE (prev_hash),
    CONSTRAINT uq_clinical_events_event_hash UNIQUE (event_hash)
);

CREATE TABLE IF NOT EXISTS agent_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    event_id UUID REFERENCES clinical_events(event_id),
    action VARCHAR(128) NOT NULL,
    input_state JSONB,
    output_decision JSONB,
    model_or_rule_version VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_chain_state (
    chain_id VARCHAR(64) PRIMARY KEY,
    last_event_id BIGINT REFERENCES clinical_events(id),
    last_hash VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chain_verification_logs (
    id BIGSERIAL PRIMARY KEY,
    chain_id VARCHAR(64) NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL,
    valid BOOLEAN NOT NULL,
    events_checked INTEGER NOT NULL DEFAULT 0,
    first_invalid_event_id UUID,
    first_invalid_position BIGINT,
    head_hash VARCHAR(64),
    reason TEXT,
    verifier_version VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clinical_events_patient_type_ts
    ON clinical_events (patient_id, event_type, device_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_clinical_events_ward_ts
    ON clinical_events (ward_id, device_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_clinical_events_sync_id
    ON clinical_events (client_sync_id);

CREATE INDEX IF NOT EXISTS ix_clinical_events_corrects_event_id
    ON clinical_events (corrects_event_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM event_chain_state WHERE chain_id = 'clinical_events'
    ) THEN
        IF EXISTS (SELECT 1 FROM clinical_events) THEN
            RAISE EXCEPTION
                'Existing clinical_events require backend/scripts/migrate_integrity.py';
        END IF;
        INSERT INTO event_chain_state
            (chain_id, last_event_id, last_hash, updated_at)
        VALUES
            ('clinical_events', NULL, repeat('0', 64), CURRENT_TIMESTAMP);
    END IF;
END;
$$;

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

DROP TRIGGER IF EXISTS trg_clinical_events_chain_link ON clinical_events;
CREATE TRIGGER trg_clinical_events_chain_link
BEFORE INSERT ON clinical_events
FOR EACH ROW EXECUTE FUNCTION vigil_validate_chain_link();

DROP TRIGGER IF EXISTS trg_clinical_events_chain_head ON clinical_events;
CREATE TRIGGER trg_clinical_events_chain_head
AFTER INSERT ON clinical_events
FOR EACH ROW EXECUTE FUNCTION vigil_update_chain_head();

DROP TRIGGER IF EXISTS trg_clinical_events_no_update ON clinical_events;
CREATE TRIGGER trg_clinical_events_no_update
BEFORE UPDATE ON clinical_events
FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_clinical_events_no_delete ON clinical_events;
CREATE TRIGGER trg_clinical_events_no_delete
BEFORE DELETE ON clinical_events
FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_clinical_events_no_truncate ON clinical_events;
CREATE TRIGGER trg_clinical_events_no_truncate
BEFORE TRUNCATE ON clinical_events
FOR EACH STATEMENT EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_agent_audit_logs_no_update ON agent_audit_logs;
CREATE TRIGGER trg_agent_audit_logs_no_update
BEFORE UPDATE ON agent_audit_logs
FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_agent_audit_logs_no_delete ON agent_audit_logs;
CREATE TRIGGER trg_agent_audit_logs_no_delete
BEFORE DELETE ON agent_audit_logs
FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_agent_audit_logs_no_truncate ON agent_audit_logs;
CREATE TRIGGER trg_agent_audit_logs_no_truncate
BEFORE TRUNCATE ON agent_audit_logs
FOR EACH STATEMENT EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_chain_verification_logs_no_update ON chain_verification_logs;
CREATE TRIGGER trg_chain_verification_logs_no_update
BEFORE UPDATE ON chain_verification_logs
FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_chain_verification_logs_no_delete ON chain_verification_logs;
CREATE TRIGGER trg_chain_verification_logs_no_delete
BEFORE DELETE ON chain_verification_logs
FOR EACH ROW EXECUTE FUNCTION vigil_block_append_only_mutation();

DROP TRIGGER IF EXISTS trg_chain_verification_logs_no_truncate ON chain_verification_logs;
CREATE TRIGGER trg_chain_verification_logs_no_truncate
BEFORE TRUNCATE ON chain_verification_logs
FOR EACH STATEMENT EXECUTE FUNCTION vigil_block_append_only_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON clinical_events FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON agent_audit_logs FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON chain_verification_logs FROM PUBLIC;

CREATE OR REPLACE VIEW v_latest_nursing_rounds AS
SELECT DISTINCT ON (patient_id)
    id AS event_db_id,
    event_id,
    patient_id,
    ward_id,
    bed_number,
    staff_id,
    device_timestamp AS last_round_timestamp,
    device_tz_offset,
    ingested_at,
    payload->'vitals' AS vitals,
    payload->>'position_change' AS position_change,
    payload->>'iv_site_check' AS iv_site_check,
    raw_note
FROM clinical_events
WHERE event_type = 'nursing_round'
ORDER BY patient_id, device_timestamp DESC;

CREATE OR REPLACE VIEW v_patient_consents AS
SELECT DISTINCT ON (patient_id, payload->>'procedure_name')
    id AS event_db_id,
    event_id,
    patient_id,
    ward_id,
    staff_id,
    payload->>'procedure_name' AS procedure_name,
    payload->>'doctor_name' AS doctor_name,
    payload->'risks_explained' AS risks_explained,
    payload->>'signature_ref' AS signature_ref,
    payload->>'witness_name' AS witness_name,
    device_timestamp AS consent_captured_at
FROM clinical_events
WHERE event_type = 'consent_capture'
ORDER BY patient_id, payload->>'procedure_name', device_timestamp DESC;

CREATE OR REPLACE VIEW v_medication_order_docs AS
SELECT
    id AS event_db_id,
    event_id,
    patient_id,
    ward_id,
    staff_id,
    payload->>'medication_name' AS medication_name,
    payload->>'dosage' AS dosage,
    payload->>'route' AS route,
    payload->>'administered_at' AS administered_at,
    payload->>'verifying_nurse_id' AS verifying_nurse_id,
    device_timestamp AS logged_at
FROM clinical_events
WHERE event_type = 'medication_order_documentation'
ORDER BY device_timestamp DESC;
