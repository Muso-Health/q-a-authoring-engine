# Deploying the qa-authoring-engine (Cloud Run + shared Cloud SQL PG14)

The ordered runbook. Fixed parameters are baked into the scripts:

| | PROD | TEST |
|---|---|---|
| Project / region | `musohealth` / `us-central1` | same |
| Cloud SQL instance | `musohealth:us-central1:test` (shared PG14) | same |
| Database (the app's tables live in its `qa_authoring` schema) | `qa_authoring` | `qa_authoring_test` |
| Cloud Run service | `qa-authoring-engine` | `qa-authoring-engine-test` |
| Migration Job | `qa-authoring-migrate` | `qa-authoring-migrate-qa-authoring-test` |
| Scaling | min 0, max 2 | min 1, max 2 |
| Audio / documentation / export buckets | `musohealth-qa-authoring-{audio,docs,export}` | `musohealth-qa-authoring-{audio,docs,export}-test` |
| Artifact Registry repo | `qa-authoring` (Docker, `us-central1`) | same |
| Runtime service account | `qa-authoring-run@musohealth.iam.gserviceaccount.com` | same |
| DB roles | `qa_migrator` (privileged, DDL) · `qa_app` (non-super, DML) | same |
| Ingress | `all`, `--allow-unauthenticated` (Entra gates, not Cloud Run IAM) | same |

Image URI: `us-central1-docker.pkg.dev/musohealth/qa-authoring/qa-authoring-engine:<git-short-sha>`.

**Who runs what:** every command below is run by **you**, the operator (they need your gcloud auth
and project rights). The repo only provides the commands and the SQL. Nothing here stores a secret:
all secrets live in Secret Manager, and the scripts reference secret *names*.

**Workstation prereqs:** `gcloud`, `git`, `curl`, `jq`, `python3`; for stage 3b also `psql` and the
Cloud SQL Auth Proxy v2 (`cloud-sql-proxy`) with `gcloud auth application-default login`.

---

## Stage 1 — Provision GCP (once)

```bash
scripts/deploy/provision.sh
```

Prompts (only for secrets that do not exist yet) for the `qa_migrator` password, the `qa_app`
password and the two Entra values (tenant id, API audience). It enables the APIs, then creates:

- the Artifact Registry repo and both databases on the shared instance;
- the `qa_migrator` DB user. `qa_app` is created in SQL at stage 3b, because a user created through
  gcloud joins `cloudsqlsuperuser`, which is not least privilege;
- the runtime SA, with `roles/cloudsql.client`, `roles/aiplatform.user` (Gemini on Vertex AI),
  `roles/cloudtranslate.user` (Google Translate), and `roles/iam.serviceAccountTokenCreator` on itself
  (signed audio, documentation and export URLs on Cloud Run have no key file);
- the six buckets (uniform access, public access prevented), with `roles/storage.objectAdmin` for
  the SA on each;
- the secrets `qa-authoring-app-db-password`, `qa-authoring-migrator-url`,
  `qa-authoring-entra-tenant` and `qa-authoring-entra-audience`, each readable by the SA, and
  `qa-authoring-migrator-password`, which is **human-only**: it is never granted to the SA (it feeds
  `psql_via_proxy.sh` and the test migration Job's URL, both run by you).

Re-running it is safe: existing resources are reported as `(exists — ok)` and existing secrets are
kept, so a re-run never rotates a password behind the DB roles' back. To rotate one, add a secret
version by hand and re-run the matching step (`gcloud sql users set-password`, or stage 3b for
`qa_app`).

## Stage 2 — First deployment of each database (once per database)

The service cannot start until `qa_app` can read its tables, and the tables exist only after the
first migration. So the first time, migrate and grant before the first service deploy:

```bash
TAG=$(git rev-parse --short HEAD)
IMAGE=us-central1-docker.pkg.dev/musohealth/qa-authoring/qa-authoring-engine:${TAG}
gcloud builds submit --tag "${IMAGE}"

# 3a — Alembic, as qa_migrator over the Cloud SQL socket (one-off Cloud Run Job, same image)
QA_AUTHORING_DB_NAME=qa_authoring_test scripts/deploy/migrate_job.sh "${IMAGE}"
scripts/deploy/migrate_job.sh "${IMAGE}"

# 3b — create qa_app and grant it DML on the app schema (as qa_migrator, through the proxy)
APP_PASSWORD="$(gcloud secrets versions access latest --secret=qa-authoring-app-db-password)"
QA_AUTHORING_DB_NAME=qa_authoring_test scripts/deploy/psql_via_proxy.sh \
  scripts/deploy/grant_app_role.sql -v app_password="${APP_PASSWORD}"
scripts/deploy/psql_via_proxy.sh scripts/deploy/grant_app_role.sql -v app_password="${APP_PASSWORD}"
```

Stage 3b is one-time: tables created by later migrations inherit the grants through `ALTER DEFAULT
PRIVILEGES FOR ROLE qa_migrator`.

## Stage 3 — Build and promote (every release)

```bash
QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=<admin email> scripts/deploy/build_and_promote.sh
QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=<admin email> CONFIRM_PROD=yes scripts/deploy/build_and_promote.sh
```

It builds the image once (skipped when the tag is already in the registry), then migrates
`qa_authoring_test` (`--wait`), deploys `qa-authoring-engine-test` and verifies it (`GET /health`
must answer 2xx; the `/openapi.json` `info.version` is printed). Without `CONFIRM_PROD=yes` it stops
there. With it, the **same** image is migrated onto `qa_authoring`, deployed to
`qa-authoring-engine` and verified the same way. Migrations always run before the deploy, as a Job;
the service never migrates on start.

Each script also runs on its own (`migrate_job.sh <IMAGE>`, `deploy_service.sh <IMAGE>`, with the
`QA_AUTHORING_*` overrides shown in their headers).

### The first admin

There is no SQL bootstrap. Every startup ensures an active user with
`QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL` holding an `admin` role with every permission (it never removes
anyone). The email is passed at deploy time and never committed. Sign in with that Entra account and
`GET /me` should list every permission; grant everyone else roles from there.

### The service's environment

`deploy_service.sh` sets the whole env set in one `--set-env-vars` (it **replaces** the set on every
redeploy, so nothing may be set live-only) and one `--set-secrets`:

- Connector: `QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME`, `QA_AUTHORING_DB_USER=qa_app`,
  `QA_AUTHORING_DB_NAME` (per env), `QA_AUTHORING_DB_IP_TYPE=public`; password from
  `qa-authoring-app-db-password`.
- Auth: `QA_AUTHORING_AUTH_PROVIDER=entra`; tenant and audience from the `qa-authoring-entra-*`
  secrets; `QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL`.
- `QA_AUTHORING_CORS_ALLOWED_ORIGINS`: the same list for both environments. It defaults to
  `http://localhost:4200`; pass the SPA's deployed origins (comma-separated) or change the default.
- Models: `QA_AUTHORING_LLM_PROVIDER=gemini` on Vertex AI (`musohealth`, `us-central1`,
  `gemini-2.5-flash`, 30 s) and `QA_AUTHORING_GOOGLE_TRANSLATE_PROJECT=musohealth` (`global`).
- Storage: the `gcs` backend for audio, documentation and exports, with the per-env buckets.

## Gotchas

- **allUsers invoker blocked?** If an org policy (domain-restricted sharing) rejects
  `--allow-unauthenticated`, the deploy fails setting the IAM policy. Grant `roles/run.invoker` to
  `allUsers` out-of-band, or put the service behind a load balancer: the browser SPA must reach it.
- **Image pull denied?** Grant `roles/artifactregistry.reader` to the Cloud Run service agent
  (`service-<PROJECT_NUMBER>@serverless-robot-prod.iam.gserviceaccount.com`).
- **Private-IP instance?** The scripts assume the instance has a public IP (the Connector default, no
  VPC). If it is private-IP only, add Direct VPC egress to the service and set
  `QA_AUTHORING_DB_IP_TYPE=private`.
- **Upload size.** Cloud Run caps an HTTP/1 request body at 32 MiB, below the documentation upload
  limit (`QA_AUTHORING_DOCUMENTATION_MAX_UPLOAD_BYTES`, 100 MiB by default): larger files are refused
  by Cloud Run before they reach the app.
- **The service would not start after a fresh database?** Stage 3b has not run on it: `qa_app` has no
  access to the schema yet, so the startup seeding fails.
