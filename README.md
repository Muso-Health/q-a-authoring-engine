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
- **pytest**, **httpx** (`TestClient`) and **testcontainers** for tests; **ruff** for linting and
  formatting; **mypy** (strict) for type checking

## Getting started

### 1. Create a virtual environment and install dependencies

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

Example `.env` for local development:

```dotenv
QA_AUTHORING_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/qa_authoring
QA_AUTHORING_CORS_ALLOWED_ORIGINS=http://localhost:4200
```

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

### 5. Run the tests

```bash
pytest -m "not integration"     # unit and API tests: no database needed
pytest -m integration           # integration tests: need PostgreSQL
pytest                          # everything
```

Integration tests run against a real PostgreSQL. By default they start a throwaway Postgres 14 container
through testcontainers, which requires a running Docker daemon. To use an existing database instead, set
`QA_AUTHORING_TEST_DATABASE_URL` to an asyncpg DSN. Without either, the integration tests are skipped.

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
