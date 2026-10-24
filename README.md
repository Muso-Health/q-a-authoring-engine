# Q&A Authoring Engine

A multilingual Q&A authoring backend that produces and validates a clinically-reviewed question-and-answer
corpus. Authors draft questions and answers across any number of languages, and the engine carries them
through review so that only clinically validated content makes it into the published corpus. It is a
FastAPI service over PostgreSQL, built with domain-driven design and a hexagonal (ports and adapters)
architecture.

> **Status: early development.** The API, data model and migrations are still changing and are not yet
> stable.

## Tech stack

- **Python 3.12**
- **FastAPI** + **uvicorn** for the HTTP API, with **Pydantic** schemas
- **PostgreSQL** via **SQLAlchemy** (async, `asyncpg`)
- **Alembic** for schema migrations
- **pydantic-settings** for environment-driven configuration
- **Cloud SQL Python Connector**, optional, for Google Cloud SQL deployments
- **Google Cloud Storage** for audio recordings (the database keeps only references)
- **ffmpeg** (`ffprobe`) to read the duration and type of uploaded recordings
- **pytest**, **httpx** (`TestClient`) and **testcontainers** for tests; **ruff** for linting and
  formatting; **mypy** (strict) for type checking

## Getting started

### 1. Create a virtual environment and install dependencies

Audio uploads need **ffmpeg** on the machine running the API, as `ffprobe` is used to
read each recording's duration and container (browser MediaRecorder webm/opus and ogg/opus,
as well as wav, mp3 and m4a). Install it with your package manager, for example
`sudo apt install ffmpeg` or `brew install ffmpeg`. The Docker image already includes it.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

All runtime and development dependencies are declared in `pyproject.toml`.

### 2. Configure the environment

Configuration is read from environment variables with the `QA_AUTHORING_` prefix, or from a local `.env`
file (git-ignored). Every variable has a development default.

| Variable | Default | Purpose |
|---|---|---|
| `QA_AUTHORING_DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/qa_authoring` | Plain asyncpg DSN, used for local development and tests. Ignored when the Cloud SQL connector is enabled. |
| `QA_AUTHORING_DB_SCHEMA` | `qa_authoring` | PostgreSQL schema the app's tables and Alembic's version table live in, isolated from other tables in the same database. Must be a lowercase identifier other than `public`. |
| `QA_AUTHORING_DB_POOL_SIZE` | `5` | Connection pool size. |
| `QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME` | *(empty)* | Cloud SQL instance (`project:region:instance`). Setting it switches the connection to the Cloud SQL Python Connector. |
| `QA_AUTHORING_DB_USER` | `qa_authoring_app` | Database user (Cloud SQL connector only). |
| `QA_AUTHORING_DB_PASSWORD` | *(empty)* | Database password (Cloud SQL connector only). Supply it from a secret store and never commit it. |
| `QA_AUTHORING_DB_NAME` | `qa_authoring` | Database name (Cloud SQL connector only). |
| `QA_AUTHORING_DB_IP_TYPE` | `public` | `public` or `private` Cloud SQL IP (Cloud SQL connector only). |
| `QA_AUTHORING_CORS_ALLOWED_ORIGINS` | *(empty)* | Comma-separated browser origins allowed to call the API (e.g. `http://localhost:4200`). Empty disables CORS. |
| `QA_AUTHORING_AUDIO_STORAGE_BACKEND` | `local` | Where recordings are stored: `local` (filesystem, for development) or `gcs` (Google Cloud Storage). |
| `QA_AUTHORING_AUDIO_BUCKET` | *(empty)* | GCS bucket for recordings. Required when the backend is `gcs`. |
| `QA_AUTHORING_AUDIO_OBJECT_PREFIX` | `audio/` | Object key prefix. Keys are this prefix plus the recording's SHA-256, so identical uploads share one object. |
| `QA_AUTHORING_AUDIO_LOCAL_DIRECTORY` | `.audio-storage` | Directory for the `local` backend (git-ignored). |
| `QA_AUTHORING_AUDIO_PLAYBACK_URL_TTL_SECONDS` | `900` | Lifetime of the signed playback URLs. |
| `QA_AUTHORING_AUDIO_MAX_UPLOAD_BYTES` | `10485760` | Largest accepted upload (10 MiB). |
| `QA_AUTHORING_AUDIO_ALLOWED_MIME_TYPES` | `audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4` | Comma-separated whitelist, checked against the type detected from the bytes (not the type the client claims). |
| `QA_AUTHORING_AUDIO_FFPROBE_PATH` | `ffprobe` | Path to the `ffprobe` binary. |
| `QA_AUTHORING_DOCUMENTATION_STORAGE_BACKEND` | `local` | Where theme documentation files are stored: `local` or `gcs`. |
| `QA_AUTHORING_DOCUMENTATION_BUCKET` | *(empty)* | GCS bucket for documentation. Required with `gcs`. |
| `QA_AUTHORING_DOCUMENTATION_OBJECT_PREFIX` | `documentation/` | Object key prefix (keys end with the file's SHA-256). |
| `QA_AUTHORING_DOCUMENTATION_LOCAL_DIRECTORY` | `.documentation-storage` | Directory for the `local` backend (git-ignored). |
| `QA_AUTHORING_DOCUMENTATION_DOWNLOAD_URL_TTL_SECONDS` | `900` | Lifetime of signed download URLs. |
| `QA_AUTHORING_DOCUMENTATION_MAX_UPLOAD_BYTES` | `104857600` | Largest accepted document (100 MiB). |
| `QA_AUTHORING_DOCUMENTATION_ALLOWED_MIME_TYPES` | PDF, Word (docx), plain text, mp4/webm/quicktime video, png/jpeg/webp images | Comma-separated whitelist of document types. |
| `QA_AUTHORING_EXPORT_STORAGE_BACKEND` | `local` | Where Parquet corpus exports are stored: `local` or `gcs`. |
| `QA_AUTHORING_EXPORT_BUCKET` | *(empty)* | GCS bucket for exports. Required with `gcs`. |
| `QA_AUTHORING_EXPORT_OBJECT_PREFIX` | `exports/` | Object key prefix (keys end with the file's SHA-256). |
| `QA_AUTHORING_EXPORT_LOCAL_DIRECTORY` | `.export-storage` | Directory for the `local` backend (git-ignored). |
| `QA_AUTHORING_EXPORT_DOWNLOAD_URL_TTL_SECONDS` | `900` | Lifetime of the signed export download URLs. |
| `QA_AUTHORING_AUTH_PROVIDER` | `entra` | How callers are identified: `entra` (a Microsoft Entra ID bearer token in `Authorization`) or `dev` (a plain `X-Dev-User: <email>` header; **local development only**, as anyone can claim any identity with it). |
| `QA_AUTHORING_AUTH_ENTRA_TENANT` | *(empty)* | The Entra tenant (directory) id. Tokens must be v2 tokens issued by `https://login.microsoftonline.com/<tenant>/v2.0`; signing keys come from that tenant's JWKS. Required with `entra`. |
| `QA_AUTHORING_AUTH_ENTRA_AUDIENCE` | *(empty)* | The token audience: the API's app registration client id (or its application ID URI). Required with `entra`; the API refuses to start without it. |
| `QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL` | *(empty)* | When set, every startup ensures an `admin` role holding every permission, and an active user with this email holding it. |
| `QA_AUTHORING_LLM_PROVIDER` | `gemini` | The language model behind the `llm` translation engine (and, later, variant generation). |
| `QA_AUTHORING_LLM_MODEL` | `gemini-2.5-flash` | Model name. |
| `QA_AUTHORING_LLM_PROJECT` / `QA_AUTHORING_LLM_LOCATION` | *(empty)* / `us-central1` | Vertex AI project and region (Application Default Credentials). |
| `QA_AUTHORING_LLM_API_KEY` | *(empty)* | Use the Gemini API with this key instead of Vertex AI. |
| `QA_AUTHORING_LLM_TIMEOUT_SECONDS` | `30` | Upper bound on one model call. |
| `QA_AUTHORING_GOOGLE_TRANSLATE_PROJECT` / `QA_AUTHORING_GOOGLE_TRANSLATE_LOCATION` | *(empty)* / `global` | Google Cloud Translation project and location for the `google` engine (Application Default Credentials). |

Example `.env` for local development:

```dotenv
QA_AUTHORING_AUTH_PROVIDER=dev
QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL=you@example.org
QA_AUTHORING_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/qa_authoring
QA_AUTHORING_CORS_ALLOWED_ORIGINS=http://localhost:4200
```

With the `gcs` backend the API uses Application Default Credentials. Its service account
needs `roles/storage.objectAdmin` on the bucket, and, to sign playback URLs without a key
file (as on Cloud Run), `roles/iam.serviceAccountTokenCreator` on itself. With the `local`
backend the playback URL is the file's `file://` URI, which is only useful for development.

### 3. Run the migrations

Alembic reads the same settings as the app. It creates the configured schema if needed and applies every
revision to it:

```bash
alembic upgrade head
```

### 4. Run the API

The ASGI entrypoint is `main:app` in `src/`:

```bash
PYTHONPATH=src uvicorn main:app --reload
```

The liveness probe is `GET /health`, and interactive API docs are served at `/docs`.

Every other endpoint requires an authenticated, **provisioned** user: the identity's email must
belong to an active user created by an administrator (no self-sign-up). Reads need nothing more;
each write needs a permission from the fixed catalogue (`GET /permissions`), granted through
roles. `GET /me` returns the current user's effective permissions. To get in the first time,
set `QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL`; with the `dev` provider, send `X-Dev-User: <that email>`.

The prompts sent to language models (translation, question-variant generation) are
organization-wide templates under `/prompt-templates`: one active template per use, readable
by everyone and editable with the `manage_prompts` permission. Each startup seeds a default
for any use that has none, and never overwrites an edited template. Templates use named
placeholders such as `{text}`, must use exactly the placeholders their use requires, and
write literal braces as `{{` and `}}`.

To run it in Docker instead (ffmpeg included):

```bash
docker build -t qa-authoring-engine .
docker run --rm -p 8080:8080 --env-file .env qa-authoring-engine
```

### 5. Run the tests

```bash
pytest -m "not integration"     # unit and API tests: no database needed
pytest -m integration           # integration tests: need PostgreSQL
pytest                          # everything
```

Integration tests run against a real PostgreSQL. By default they start a throwaway Postgres 14 container
through testcontainers, which requires a running Docker daemon. To use an existing database instead, set
`QA_AUTHORING_TEST_DATABASE_URL` to an asyncpg DSN. Without either, the integration tests are skipped.

The tests of the `ffprobe` adapter against the real binary run when `ffprobe` is on `PATH` and are
skipped otherwise.

Linting and type checking:

```bash
ruff check src tests
ruff format --check .
mypy src tests
```

## Project layout

```
src/
├── main.py                      # composition root: uvicorn main:app
├── qa_authoring/
│   ├── domain/                  # entities, value objects, invariants; pure Python, no I/O
│   │   ├── model/
│   │   └── value_objects/
│   ├── application/             # use cases (one package per command/query + handler)
│   │   └── ports/               # interfaces the use cases depend on (repositories, unit of work)
│   └── infrastructure/
│       └── persistence/         # SQLAlchemy adapters, tables, unit of work, engine factories
├── apps/
│   └── api/                     # FastAPI app factory, routers, schemas, error mapping
└── config/                      # settings and the DI container
migrations/                      # Alembic environment and revisions
tests/                           # mirrors the src tree
```

Dependencies point inward. `domain` depends on nothing, `application` depends on `domain` and its own
ports, and `infrastructure` and `apps` depend on those. `config` and `main.py` wire everything together.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). Copyright 2026 Muso.
