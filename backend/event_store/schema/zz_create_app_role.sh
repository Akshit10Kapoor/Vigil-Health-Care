#!/bin/sh
set -eu

if [ -z "${VIGIL_APP_DB_PASSWORD:-}" ]; then
    echo "ERROR: VIGIL_APP_DB_PASSWORD must be set before database initialization" >&2
    exit 1
fi

APP_ROLE="${VIGIL_APP_DB_ROLE:-vigil_app}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v app_role="$APP_ROLE" -v app_password="$VIGIL_APP_DB_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_role', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'app_role', :'app_password') \gexec

GRANT USAGE ON SCHEMA public TO :"app_role";

REVOKE ALL ON clinical_events FROM :"app_role";
GRANT SELECT, INSERT ON clinical_events TO :"app_role";
REVOKE UPDATE, DELETE, TRUNCATE ON clinical_events FROM :"app_role";

REVOKE ALL ON event_chain_state FROM :"app_role";
GRANT SELECT ON event_chain_state TO :"app_role";

REVOKE ALL ON agent_audit_logs FROM :"app_role";
GRANT SELECT, INSERT ON agent_audit_logs TO :"app_role";
REVOKE UPDATE, DELETE, TRUNCATE ON agent_audit_logs FROM :"app_role";

REVOKE ALL ON chain_verification_logs FROM :"app_role";
GRANT SELECT, INSERT ON chain_verification_logs TO :"app_role";
REVOKE UPDATE, DELETE, TRUNCATE ON chain_verification_logs FROM :"app_role";

GRANT SELECT, INSERT ON wards TO :"app_role";
GRANT SELECT, INSERT ON staff TO :"app_role";
GRANT SELECT, INSERT ON patients TO :"app_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_role";

GRANT EXECUTE ON FUNCTION vigil_validate_chain_link() TO :"app_role";
GRANT EXECUTE ON FUNCTION vigil_update_chain_head() TO :"app_role";
GRANT EXECUTE ON FUNCTION vigil_block_append_only_mutation() TO :"app_role";
EOSQL
