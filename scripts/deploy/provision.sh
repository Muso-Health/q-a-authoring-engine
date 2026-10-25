#!/usr/bin/env bash
set -euo pipefail

# ── Stage 1: GCP provisioning for the qa-authoring-engine ────────────────────────────────────────
# YOU run this once (it needs your gcloud auth and project rights). It is idempotent: an "already
# exists" on a create is safe and reported as "(exists — ok)", and a secret that already exists is
# kept as is — so a re-run never rotates a password behind the DB roles' back. Passwords and Entra
# values are read from prompts, so they never land in your shell history or in this file — only in
# Secret Manager. Both environments (prod and test) are provisioned in the same run: they share the
# runtime SA, the secrets, the Entra config and the Artifact Registry repo, and each gets its own
# database and its own three buckets.
#
# Prereq: gcloud CLI authenticated (`gcloud auth login`) with rights on the project.

PROJECT_ID="musohealth"
REGION="us-central1"
INSTANCE_CONNECTION_NAME="musohealth:us-central1:test"   # project:region:instance (the shared PG14)
PROD_DB="qa_authoring"
TEST_DB="qa_authoring_test"
AR_REPO="qa-authoring"                                    # Artifact Registry Docker repo
RUNTIME_SA="qa-authoring-run"                             # runtime service account id (no domain)
MIGRATOR_USER="qa_migrator"                               # privileged DB role (DDL) — created here
APP_USER="qa_app"                                         # least-privilege DB role — created in SQL
# Per environment: audio recordings, theme documentation, Parquet corpus exports.
BUCKETS=(
  musohealth-qa-authoring-audio musohealth-qa-authoring-docs musohealth-qa-authoring-export
  musohealth-qa-authoring-audio-test musohealth-qa-authoring-docs-test musohealth-qa-authoring-export-test
)

SA_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
INSTANCE_NAME="${INSTANCE_CONNECTION_NAME##*:}"           # last segment == the instance id

gcloud config set project "${PROJECT_ID}"

echo "▶ Enabling APIs…"
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  iamcredentials.googleapis.com \
  aiplatform.googleapis.com \
  translate.googleapis.com

echo "▶ Artifact Registry Docker repo (${AR_REPO})…"
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker --location="${REGION}" \
  --description="Muso qa-authoring-engine images" || echo "  (exists — ok)"

for DB in "${PROD_DB}" "${TEST_DB}"; do
  echo "▶ Database ${DB} on ${INSTANCE_NAME}…"
  gcloud sql databases create "${DB}" --instance="${INSTANCE_NAME}" || echo "  (exists — ok)"
done

echo "▶ Runtime service account (${SA_EMAIL})…"
gcloud iam service-accounts create "${RUNTIME_SA}" \
  --display-name="qa-authoring-engine Cloud Run runtime" || echo "  (exists — ok)"

# Project-level roles: Cloud SQL (the Connector and the migration Job's socket), Gemini on Vertex AI
# and Google Cloud Translation (both through Application Default Credentials).
for ROLE in roles/cloudsql.client roles/aiplatform.user roles/cloudtranslate.user; do
  echo "▶ IAM: ${ROLE} on the runtime SA…"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}" --condition=None >/dev/null
done

# Signed playback/download URLs on Cloud Run have no key file: the SA signs through the IAM
# signBlob API, which needs Token Creator on ITSELF.
echo "▶ IAM: Token Creator for the runtime SA on itself (signed URLs)…"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/iam.serviceAccountTokenCreator" >/dev/null

for BUCKET in "${BUCKETS[@]}"; do
  echo "▶ Bucket gs://${BUCKET}…"
  gcloud storage buckets create "gs://${BUCKET}" --location="${REGION}" \
    --uniform-bucket-level-access --public-access-prevention || echo "  (exists — ok)"
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectAdmin" >/dev/null
done

# ── Secrets ──────────────────────────────────────────────────────────────────────────────────────
secret_exists () {  # name
  gcloud secrets describe "$1" >/dev/null 2>&1
}
put_secret () {  # name value : create it (callers only reach here when it does not exist yet)
  printf '%s' "$2" | gcloud secrets create "$1" --replication-policy=automatic --data-file=- >/dev/null
  echo "   secret $1 ✓"
}
grant_sa () {  # name : let the runtime SA read this secret
  gcloud secrets add-iam-policy-binding "$1" \
    --member="serviceAccount:${SA_EMAIL}" --role="roles/secretmanager.secretAccessor" >/dev/null
}
url_encode () {  # reads the value on stdin, so it never shows in the process list
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=""))'
}

echo "▶ Migrator DB user (${MIGRATOR_USER}) — privileged, runs Alembic…"
if secret_exists qa-authoring-migrator-password; then
  echo "  (secret qa-authoring-migrator-password exists — kept; the user is left untouched)"
else
  read -rsp "   Enter a NEW password for ${MIGRATOR_USER}: " MIGRATOR_PASSWORD; echo
  gcloud sql users create "${MIGRATOR_USER}" --instance="${INSTANCE_NAME}" \
    --password="${MIGRATOR_PASSWORD}" || echo "  (exists — ok; re-setting its password)"
  gcloud sql users set-password "${MIGRATOR_USER}" --instance="${INSTANCE_NAME}" \
    --password="${MIGRATOR_PASSWORD}"
  # The prod migration Job connects over the built-in Cloud SQL socket, so it needs a full URL;
  # Alembic reads it from QA_AUTHORING_DATABASE_URL. The test Job builds its own from the password.
  ENCODED="$(printf '%s' "${MIGRATOR_PASSWORD}" | url_encode)"
  MIGRATOR_URL="postgresql+asyncpg://${MIGRATOR_USER}:${ENCODED}@/${PROD_DB}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"
  put_secret qa-authoring-migrator-password "${MIGRATOR_PASSWORD}"  # human-only; NOT granted to the SA
  if ! secret_exists qa-authoring-migrator-url; then put_secret qa-authoring-migrator-url "${MIGRATOR_URL}"; fi
fi
grant_sa qa-authoring-migrator-url

# The service connects via the Cloud SQL Connector — it needs only the password (user, database and
# instance are plain env on the service). The role itself is created by grant_app_role.sql: a user
# created through gcloud would join cloudsqlsuperuser, which is not least privilege.
echo "▶ App runtime password (for ${APP_USER}, created later in grant_app_role.sql)…"
if secret_exists qa-authoring-app-db-password; then
  echo "  (secret qa-authoring-app-db-password exists — kept)"
else
  read -rsp "   Enter a NEW password for ${APP_USER}: " APP_PASSWORD; echo
  put_secret qa-authoring-app-db-password "${APP_PASSWORD}"
fi
grant_sa qa-authoring-app-db-password

echo "▶ Entra secrets — the API's app registration (tokens must be v2, issued by"
echo "   https://login.microsoftonline.com/<tenant>/v2.0)…"
if secret_exists qa-authoring-entra-tenant; then
  echo "  (secret qa-authoring-entra-tenant exists — kept)"
else
  read -rp "   QA_AUTHORING_AUTH_ENTRA_TENANT   (the tenant/directory id GUID): " ENTRA_TENANT
  put_secret qa-authoring-entra-tenant "${ENTRA_TENANT}"
fi
grant_sa qa-authoring-entra-tenant
if secret_exists qa-authoring-entra-audience; then
  echo "  (secret qa-authoring-entra-audience exists — kept)"
else
  read -rp "   QA_AUTHORING_AUTH_ENTRA_AUDIENCE (the API's client id, or api://<client-id>): " ENTRA_AUDIENCE
  put_secret qa-authoring-entra-audience "${ENTRA_AUDIENCE}"
fi
grant_sa qa-authoring-entra-audience

echo
echo "✅ Stage 1 done. Next, once per database: migrate, then grant_app_role.sql (see the README)."
