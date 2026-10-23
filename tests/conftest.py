from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from qa_authoring.infrastructure.persistence.engine import LocalDsnEngineFactory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """An asyncpg URL to a throwaway PostgreSQL for the integration suite.

    ``QA_AUTHORING_TEST_DATABASE_URL`` wins when set (CI service, docker compose); otherwise one
    Postgres 14 testcontainer for the whole session, matching production. Without either, the
    integration tests are skipped rather than failed — there is no database to test against.
    """
    explicit = os.environ.get("QA_AUTHORING_TEST_DATABASE_URL")
    if explicit:
        yield explicit
        return
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:14", driver="asyncpg")
        container.start()
    except Exception as exc:  # Docker absent or unreachable
        pytest.skip(f"no PostgreSQL available for integration tests: {exc}")
    try:
        yield str(container.get_connection_url())
    finally:
        container.stop()


REPO_SCHEMA = "qa_authoring_repo_it"


@pytest.fixture(scope="session")
def migrated_url(postgres_url: str) -> str:
    """The integration database with ``alembic upgrade head`` applied to a dedicated schema —
    the adapters are exercised against the migrated schema, never a create_all approximation."""
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    overrides = {"QA_AUTHORING_DATABASE_URL": postgres_url, "QA_AUTHORING_DB_SCHEMA": REPO_SCHEMA}
    saved = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        command.upgrade(config, "head")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return postgres_url


@pytest.fixture
async def migrated_engine(migrated_url: str) -> AsyncIterator[AsyncEngine]:
    """An engine pinned to the migrated schema, emptied before each test."""
    factory = LocalDsnEngineFactory(database_url=migrated_url, schema=REPO_SCHEMA)
    async with factory.engine() as engine:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE themes, protocols, projects, languages"))
        yield engine
