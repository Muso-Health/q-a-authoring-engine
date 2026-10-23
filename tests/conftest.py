from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


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
