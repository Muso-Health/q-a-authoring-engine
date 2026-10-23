from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "qa_authoring_it"


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


async def _query(url: str, sql: str) -> list[tuple[object, ...]]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return [tuple(row) for row in (await connection.execute(text(sql))).all()]
    finally:
        await engine.dispose()


def test_upgrade_head_creates_the_app_schema_and_stamps_it(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Alembic reads the same Settings as the app: the DSN and schema come from QA_AUTHORING_ env.
    The version table lives in the app's own schema, never in ``public``."""
    monkeypatch.setenv("QA_AUTHORING_DATABASE_URL", postgres_url)
    monkeypatch.setenv("QA_AUTHORING_DB_SCHEMA", SCHEMA)
    monkeypatch.delenv("QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME", raising=False)

    command.upgrade(_alembic_config(), "head")

    schemas = asyncio.run(
        _query(postgres_url, f"SELECT 1 FROM pg_namespace WHERE nspname = '{SCHEMA}'")
    )
    assert schemas == [(1,)]
    versions = asyncio.run(
        _query(postgres_url, f"SELECT version_num FROM {SCHEMA}.alembic_version")
    )
    assert versions == [("0001_baseline",)]
    public_version = asyncio.run(
        _query(
            postgres_url,
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version'",
        )
    )
    assert public_version == []

    # Idempotent: a second upgrade is a no-op, and the baseline downgrades cleanly.
    command.upgrade(_alembic_config(), "head")
    command.downgrade(_alembic_config(), "base")
    assert (
        asyncio.run(_query(postgres_url, f"SELECT version_num FROM {SCHEMA}.alembic_version")) == []
    )
