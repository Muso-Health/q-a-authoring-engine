from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

import qa_authoring.infrastructure.persistence.schema.access
import qa_authoring.infrastructure.persistence.schema.catalog
import qa_authoring.infrastructure.persistence.schema.category
import qa_authoring.infrastructure.persistence.schema.documentation
import qa_authoring.infrastructure.persistence.schema.intent
import qa_authoring.infrastructure.persistence.schema.language
import qa_authoring.infrastructure.persistence.schema.prompt_template
import qa_authoring.infrastructure.persistence.schema.qaset
import qa_authoring.infrastructure.persistence.schema.validation  # noqa: F401
from config.database import engine_factory_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.persistence.metadata import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata

# The same Settings as the app: the DSN (or Cloud SQL Connector fields) and the target schema all
# come from QA_AUTHORING_ env, so a migration can never hit a different database or schema than the
# app reads. The version table lives in the app's schema, never in ``public``.
settings = Settings()
schema = settings.db_schema


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        version_table_schema=schema,
    )
    with context.begin_transaction():
        context.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        context.execute(f'SET search_path TO "{schema}"')
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
        version_table_schema=schema,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Through the same engine factory as the app (search_path pinned to the schema). The schema is
    # created first, committed on its own, so the version table and every revision can land in it.
    async with (
        engine_factory_from_settings(settings).engine() as engine,
        engine.connect() as connection,
    ):
        await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await connection.commit()
        await connection.run_sync(_do_run_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
