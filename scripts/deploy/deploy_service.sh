#!/usr/bin/env bash
set -euo pipefail

# ── Stage 4: deploy the API to Cloud Run ─────────────────────────────────────────────────────────
# YOU run this (or build_and_promote.sh does), passing the image URI. The service connects to Cloud
# SQL via the Python Connector (QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME is set, so the app picks
# that path) as the least-privilege qa_app role. Ingress is `all` and Cloud Run IAM auth is OFF
# (--allow-unauthenticated): the SPA calls from the browser with an Entra bearer token, which the
# app's own Entra validation gates — Cloud Run's IAM layer must not also demand a Google identity.
#
#   QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=<admin email> \
#     scripts/deploy/deploy_service.sh us-central1-docker.pkg.dev/musohealth/qa-authoring/qa-authoring-engine:<tag>
#
# The test environment sets its service, database and bucket names (and its instance floor);
# everything else — runtime SA, secrets, Entra config, model config and the CORS list — is shared:
#   QA_AUTHORING_SERVICE=qa-authoring-engine-test QA_AUTHORING_DB_NAME=qa_authoring_test \
#     QA_AUTHORING_MIN_INSTANCES=1 QA_AUTHORING_AUDIO_BUCKET=musohealth-qa-authoring-audio-test \
#     QA_AUTHORING_DOCUMENTATION_BUCKET=musohealth-qa-authoring-docs-test \
#     QA_AUTHORING_EXPORT_BUCKET=musohealth-qa-authoring-export-test \
#     QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=<admin email> scripts/deploy/deploy_service.sh <IMAGE_URI>

IMAGE="${1:?usage: deploy_service.sh <IMAGE_URI>}"

PROJECT_ID="musohealth"
REGION="us-central1"
INSTANCE_CONNECTION_NAME="musohealth:us-central1:test"
SERVICE="${QA_AUTHORING_SERVICE:-qa-authoring-engine}"     # overridable; default is prod
DB_NAME="${QA_AUTHORING_DB_NAME:-qa_authoring}"            # overridable; default is prod
MIN_INSTANCES="${QA_AUTHORING_MIN_INSTANCES:-0}"           # test uses 1 (warm)
MAX_INSTANCES="${QA_AUTHORING_MAX_INSTANCES:-2}"
AUDIO_BUCKET="${QA_AUTHORING_AUDIO_BUCKET:-musohealth-qa-authoring-audio}"
DOCUMENTATION_BUCKET="${QA_AUTHORING_DOCUMENTATION_BUCKET:-musohealth-qa-authoring-docs}"
EXPORT_BUCKET="${QA_AUTHORING_EXPORT_BUCKET:-musohealth-qa-authoring-export}"
RUNTIME_SA="qa-authoring-run@musohealth.iam.gserviceaccount.com"
APP_USER="qa_app"

# Every startup ensures an active admin holding every permission with this email — the first way in,
# no SQL bootstrap. Required: --set-env-vars REPLACES the whole env-var set on each redeploy, so it is
# reasserted every time rather than set live-only. Passed in, never committed (this repo is public).
BOOTSTRAP_ADMIN_EMAIL="${QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL:?set QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL to the first admin email}"

# The SAME list for every environment; add the SPA's deployed origins here (or pass the whole list).
CORS_ORIGINS="${QA_AUTHORING_CORS_ALLOWED_ORIGINS:-http://localhost:4200}"

# Language models — shared across environments. No secrets among them: Gemini on Vertex AI and
# Google Cloud Translation both authenticate with the runtime service account (ADC).
LLM_PROVIDER="gemini"
LLM_PROJECT="musohealth"
LLM_LOCATION="us-central1"
LLM_MODEL="gemini-2.5-flash"
LLM_TIMEOUT_SECONDS="30"
GOOGLE_TRANSLATE_PROJECT="musohealth"
GOOGLE_TRANSLATE_LOCATION="global"

gcloud config set project "${PROJECT_ID}"

# `^@^` sets `@` as the env-var separator, so the comma-containing CORS list stays a single value.
# All env vars go through this ONE --set-env-vars so the full set is reasserted on every redeploy.
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --service-account="${RUNTIME_SA}" \
  --add-cloudsql-instances="${INSTANCE_CONNECTION_NAME}" \
  --min-instances="${MIN_INSTANCES}" \
  --max-instances="${MAX_INSTANCES}" \
  --ingress=all \
  --allow-unauthenticated \
  --port=8080 \
  --cpu-boost \
  --set-env-vars="^@^QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME=${INSTANCE_CONNECTION_NAME}@QA_AUTHORING_DB_USER=${APP_USER}@QA_AUTHORING_DB_NAME=${DB_NAME}@QA_AUTHORING_DB_IP_TYPE=public@QA_AUTHORING_CORS_ALLOWED_ORIGINS=${CORS_ORIGINS}@QA_AUTHORING_AUTH_PROVIDER=entra@QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=${BOOTSTRAP_ADMIN_EMAIL}@QA_AUTHORING_LLM_PROVIDER=${LLM_PROVIDER}@QA_AUTHORING_LLM_PROJECT=${LLM_PROJECT}@QA_AUTHORING_LLM_LOCATION=${LLM_LOCATION}@QA_AUTHORING_LLM_MODEL=${LLM_MODEL}@QA_AUTHORING_LLM_TIMEOUT_SECONDS=${LLM_TIMEOUT_SECONDS}@QA_AUTHORING_GOOGLE_TRANSLATE_PROJECT=${GOOGLE_TRANSLATE_PROJECT}@QA_AUTHORING_GOOGLE_TRANSLATE_LOCATION=${GOOGLE_TRANSLATE_LOCATION}@QA_AUTHORING_AUDIO_STORAGE_BACKEND=gcs@QA_AUTHORING_AUDIO_BUCKET=${AUDIO_BUCKET}@QA_AUTHORING_DOCUMENTATION_STORAGE_BACKEND=gcs@QA_AUTHORING_DOCUMENTATION_BUCKET=${DOCUMENTATION_BUCKET}@QA_AUTHORING_EXPORT_STORAGE_BACKEND=gcs@QA_AUTHORING_EXPORT_BUCKET=${EXPORT_BUCKET}" \
  --set-secrets="QA_AUTHORING_DB_PASSWORD=qa-authoring-app-db-password:latest,QA_AUTHORING_AUTH_ENTRA_TENANT=qa-authoring-entra-tenant:latest,QA_AUTHORING_AUTH_ENTRA_AUDIENCE=qa-authoring-entra-audience:latest"

echo "✅ Deployed. Service URL:"
gcloud run services describe "${SERVICE}" --region="${REGION}" --format="value(status.url)"
