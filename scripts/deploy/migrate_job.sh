#!/usr/bin/env bash
set -euo pipefail

# ── Stage 3a: run Alembic migrations via a one-off Cloud Run Job ──────────────────────────────────
# YOU run this (or build_and_promote.sh does), passing the image URI. The Job uses the SAME image,
# overriding the command to `alembic upgrade head`. It connects through the built-in Cloud SQL socket
# (mounted at /cloudsql/<instance>) as the privileged migrator role, which does the DDL. Alembic's
# env.py reads the same Settings as the app: with QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME unset it
# uses the plain URL in QA_AUTHORING_DATABASE_URL — the migrator URL here — while the service keeps
# the Connector path as qa_app. The service never migrates on start.
#
#   scripts/deploy/migrate_job.sh us-central1-docker.pkg.dev/musohealth/qa-authoring/qa-authoring-engine:<tag>
#
# The test environment migrates its own database by passing its name; the job name is derived from
# it, so a test migration never touches the prod job:
#   QA_AUTHORING_DB_NAME=qa_authoring_test scripts/deploy/migrate_job.sh <IMAGE_URI>
#
# The first time per database, run grant_app_role.sql (stage 3b) after this, before the deploy.

IMAGE="${1:?usage: migrate_job.sh <IMAGE_URI>}"

PROJECT_ID="musohealth"
REGION="us-central1"
INSTANCE_CONNECTION_NAME="musohealth:us-central1:test"
RUNTIME_SA="qa-authoring-run@musohealth.iam.gserviceaccount.com"
MIGRATOR_USER="qa_migrator"
DB_NAME="${QA_AUTHORING_DB_NAME:-qa_authoring}"   # overridable; default is prod

# Job name and migrator URL by DB. Prod (default) uses the pre-stored migrator-url secret. The test
# DB gets its own job name and, since no per-DB migrator-url secret exists, builds the URL inline
# from the migrator-password secret (the URL only differs by database name). The inline URL rides in
# the job's env (visible to anyone who can read the job), which is acceptable for the test database;
# prod keeps the secret reference.
if [[ "${DB_NAME}" == "qa_authoring" ]]; then
  JOB="qa-authoring-migrate"
  URL_FLAGS=(--set-secrets="QA_AUTHORING_DATABASE_URL=qa-authoring-migrator-url:latest")
else
  JOB="qa-authoring-migrate-${DB_NAME//_/-}"
  ENCODED_PASSWORD="$(gcloud secrets versions access latest \
    --secret=qa-authoring-migrator-password --project="${PROJECT_ID}" \
    | python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=""))')"
  MIGRATOR_URL="postgresql+asyncpg://${MIGRATOR_USER}:${ENCODED_PASSWORD}@/${DB_NAME}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"
  # Single var, default comma separator: the URL contains ':' '@' '/' '?' '=' but no comma (the
  # password is percent-encoded), and gcloud splits KEY=VALUE on the first '=' only.
  URL_FLAGS=(--set-env-vars="QA_AUTHORING_DATABASE_URL=${MIGRATOR_URL}")
fi

gcloud config set project "${PROJECT_ID}"

if gcloud run jobs describe "${JOB}" --region="${REGION}" >/dev/null 2>&1; then
  VERB=update
else
  VERB=create
fi

echo "▶ ${VERB} Cloud Run Job ${JOB} (database ${DB_NAME})…"
gcloud run jobs "${VERB}" "${JOB}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --service-account="${RUNTIME_SA}" \
  --set-cloudsql-instances="${INSTANCE_CONNECTION_NAME}" \
  "${URL_FLAGS[@]}" \
  --command="alembic" \
  --args="upgrade,head" \
  --max-retries=0 \
  --task-timeout=600

echo "▶ Executing migrations (waits for completion)…"
gcloud run jobs execute "${JOB}" --region="${REGION}" --wait

echo "✅ Migrations applied to ${DB_NAME}."
