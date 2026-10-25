#!/usr/bin/env bash
set -euo pipefail

# Run a .sql file against a Cloud SQL database of this engine as the privileged migrator role, over a
# short-lived Cloud SQL Auth Proxy tunnel. Used for grant_app_role.sql (stage 3b), which must run
# once per database before the service can start. (The first admin needs no SQL: the service
# ensures QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL on startup.)
#
# Prereqs on YOUR workstation:
#   • gcloud auth application-default login          (the proxy uses ADC)
#   • the Cloud SQL Auth Proxy v2 binary on PATH as `cloud-sql-proxy`
#       https://cloud.google.com/sql/docs/postgres/connect-auth-proxy
#   • psql (the postgresql-client package)
#
# Usage:
#   scripts/deploy/psql_via_proxy.sh <sql-file> [extra psql args, e.g. -v app_password=...]
#
# Target the test database by name (defaults to prod). The DB name is also exposed to the SQL file
# as the psql variable :"db_name" (grant_app_role.sql uses it for GRANT CONNECT):
#   QA_AUTHORING_DB_NAME=qa_authoring_test scripts/deploy/psql_via_proxy.sh scripts/deploy/grant_app_role.sql -v app_password=…

SQL_FILE="${1:?usage: psql_via_proxy.sh <sql-file> [psql args…]}"; shift || true

PROJECT_ID="musohealth"
INSTANCE_CONNECTION_NAME="musohealth:us-central1:test"
DB_NAME="${QA_AUTHORING_DB_NAME:-qa_authoring}"   # overridable; default is prod
MIGRATOR_USER="qa_migrator"
PROXY_PORT="5432"

# The migrator password, from the human-only secret provision.sh stored (fallback: prompt).
MIGRATOR_PASSWORD="$(gcloud secrets versions access latest \
  --secret=qa-authoring-migrator-password --project="${PROJECT_ID}" 2>/dev/null || true)"
if [[ -z "${MIGRATOR_PASSWORD:-}" ]]; then
  read -rsp "Password for ${MIGRATOR_USER}: " MIGRATOR_PASSWORD; echo
fi

echo "▶ Starting Cloud SQL Auth Proxy on 127.0.0.1:${PROXY_PORT}…"
cloud-sql-proxy "${INSTANCE_CONNECTION_NAME}" --port "${PROXY_PORT}" &
PROXY_PID=$!
trap 'kill "${PROXY_PID}" 2>/dev/null || true' EXIT

# Wait for the tunnel to accept TCP connections (up to ~15s).
for _ in $(seq 1 30); do
  if (exec 3<>"/dev/tcp/127.0.0.1/${PROXY_PORT}") 2>/dev/null; then exec 3>&-; break; fi
  sleep 0.5
done

echo "▶ Running ${SQL_FILE} as ${MIGRATOR_USER} on ${DB_NAME}…"
PGPASSWORD="${MIGRATOR_PASSWORD}" psql \
  --host=127.0.0.1 --port="${PROXY_PORT}" \
  --username="${MIGRATOR_USER}" --dbname="${DB_NAME}" \
  --no-psqlrc --set=ON_ERROR_STOP=on --set=db_name="${DB_NAME}" \
  "$@" \
  --file="${SQL_FILE}"

echo "✅ Done."
