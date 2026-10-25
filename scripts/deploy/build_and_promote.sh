#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────────────────────
# build_and_promote.sh — build the engine image ONCE and promote the SAME artifact to TEST, then
# (gated) to PROD. Test and prod therefore run a byte-identical image; nothing is ever rebuilt
# between the two environments.
#
# It composes the existing stage scripts (no new deploy logic):
#   migrate_job.sh    — Alembic migrations as a one-off Cloud Run Job (DB by QA_AUTHORING_DB_NAME)
#   deploy_service.sh — the single shared service deploy (PROD defaults; TEST = overrides)
# The model config, CORS and the secrets are baked into deploy_service.sh, so BOTH environments
# receive them automatically — this script adds only the per-environment names.
#
# Flow: build once → migrate+deploy TEST (same image) → verify TEST →
#        GATE (CONFIRM_PROD=yes) → migrate+deploy PROD (same image) → verify PROD.
#
# Usage (QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL is required by deploy_service.sh):
#   QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=<email> scripts/deploy/build_and_promote.sh                   # TEST only
#   QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=<email> CONFIRM_PROD=yes scripts/deploy/build_and_promote.sh  # …and PROD
# ─────────────────────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="musohealth"
REGION="us-central1"
IMAGE_REPO="us-central1-docker.pkg.dev/musohealth/qa-authoring/qa-authoring-engine"
TEST_SERVICE="qa-authoring-engine-test"
PROD_SERVICE="qa-authoring-engine"
TEST_DB="qa_authoring_test"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "${HERE}" rev-parse --show-toplevel)"
CONFIRM_PROD="${CONFIRM_PROD:-no}"

# One tag = one artifact, resolved from the repo HEAD (independent of the caller CWD).
TAG="$(git -C "${HERE}" rev-parse --short HEAD)"
IMAGE="${IMAGE_REPO}:${TAG}"

log() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }

# Resolve a Cloud Run service URL, require GET /health to answer 2xx, and echo the deployed contract
# version (info.version from /openapi.json) on STDOUT; all human output goes to STDERR so the caller
# can capture just the version. Fails (non-zero) if either check fails — under set -e that aborts
# the promotion.
verify() {  # $1 = service, $2 = label
  local svc="$1" label="$2" url ver
  url="$(gcloud run services describe "${svc}" --region="${REGION}" --format='value(status.url)')"
  echo "  ${label} URL: ${url}" >&2
  if ! curl -fsS "${url}/health" >/dev/null; then
    echo "  ABORT: ${label} ${url}/health did not answer 2xx" >&2
    return 1
  fi
  echo "  ${label} /health: ok" >&2
  ver="$(curl -fsS "${url}/openapi.json" | jq -r .info.version)"
  if [[ -z "${ver}" || "${ver}" == "null" ]]; then
    echo "  ABORT: could not read ${label} contract version from ${url}/openapi.json" >&2
    return 1
  fi
  echo "  ${label} /openapi.json info.version: ${ver}" >&2
  printf '%s' "${ver}"
}

# Fail before building anything if the deploy would refuse to run.
: "${QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL:?set QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL to the first admin email}"

gcloud config set project "${PROJECT_ID}" >/dev/null

# ── 1 + 2. Build ONCE (skip if this exact tag is already in the registry) ───────────────────────
log "Image ${IMAGE}"
if gcloud artifacts docker images describe "${IMAGE}" >/dev/null 2>&1; then
  echo "Tag already present in Artifact Registry — reusing it, no rebuild."
else
  log "BUILD (one artifact promoted to both environments)"
  gcloud builds submit "${REPO_ROOT}" --tag "${IMAGE}"
fi

# ── 3. TEST: migrate its DB, deploy the SAME image with the test overrides, verify ──────────────
log "TEST: migrate database ${TEST_DB}"
QA_AUTHORING_DB_NAME="${TEST_DB}" "${HERE}/migrate_job.sh" "${IMAGE}"

log "TEST: deploy ${TEST_SERVICE} (same image; warm: MIN=1 MAX=2)"
QA_AUTHORING_SERVICE="${TEST_SERVICE}" \
  QA_AUTHORING_DB_NAME="${TEST_DB}" \
  QA_AUTHORING_MIN_INSTANCES=1 \
  QA_AUTHORING_MAX_INSTANCES=2 \
  QA_AUTHORING_AUDIO_BUCKET=musohealth-qa-authoring-audio-test \
  QA_AUTHORING_DOCUMENTATION_BUCKET=musohealth-qa-authoring-docs-test \
  QA_AUTHORING_EXPORT_BUCKET=musohealth-qa-authoring-export-test \
  "${HERE}/deploy_service.sh" "${IMAGE}"

log "TEST: verify"
TEST_VERSION="$(verify "${TEST_SERVICE}" TEST)"

# ── 4. GATE — stop here unless the operator explicitly opts into prod ───────────────────────────
# (A failed test migrate/deploy/verify has already aborted the script via set -e.)
if [[ "${CONFIRM_PROD}" != "yes" ]]; then
  log "STOP at gate: TEST promoted and verified."
  echo "Set CONFIRM_PROD=yes to promote this SAME image to PROD."
  echo "  image:        ${IMAGE}"
  echo "  TEST version: ${TEST_VERSION}"
  exit 0
fi

# ── 5. PROD: migrate its DB, deploy the SAME image with prod defaults (no overrides, no rebuild) ─
# The test overrides above were per-command, so nothing leaks into the prod calls.
log "PROD: migrate database qa_authoring"
"${HERE}/migrate_job.sh" "${IMAGE}"

log "PROD: deploy ${PROD_SERVICE} (prod defaults, SAME image — not rebuilt)"
"${HERE}/deploy_service.sh" "${IMAGE}"

log "PROD: verify"
PROD_VERSION="$(verify "${PROD_SERVICE}" PROD)"

# ── 6. Summary ──────────────────────────────────────────────────────────────────────────────────
log "SUMMARY"
printf '  image:        %s\n  TEST version: %s\n  PROD version: %s\n' \
  "${IMAGE}" "${TEST_VERSION}" "${PROD_VERSION}"
