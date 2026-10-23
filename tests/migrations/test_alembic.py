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
    assert versions == [("0007_intents",)]
    public_version = asyncio.run(
        _query(
            postgres_url,
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version'",
        )
    )
    assert public_version == []

    languages = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' AND table_name = 'languages' "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE') ORDER BY constraint_name",
        )
    )
    assert languages == [("pk_languages", "PRIMARY KEY"), ("uq_languages_code", "UNIQUE")]

    foreign_keys = asyncio.run(
        _query(
            postgres_url,
            "SELECT DISTINCT tc.constraint_name, tc.table_name, ccu.table_name, rc.delete_rule "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.referential_constraints rc "
            "ON rc.constraint_name = tc.constraint_name AND rc.constraint_schema = tc.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema "
            f"WHERE tc.table_schema = '{SCHEMA}' AND tc.constraint_type = 'FOREIGN KEY' "
            "ORDER BY tc.constraint_name",
        )
    )
    assert foreign_keys == [
        (
            "fk_answer_translation_links_answer_high_id_answers",
            "answer_translation_links",
            "answers",
            "CASCADE",
        ),
        (
            "fk_answer_translation_links_answer_low_id_answers",
            "answer_translation_links",
            "answers",
            "CASCADE",
        ),
        (
            "fk_answer_translation_links_qaset_id_qasets",
            "answer_translation_links",
            "qasets",
            "CASCADE",
        ),
        ("fk_answers_language_id_languages", "answers", "languages", "RESTRICT"),
        ("fk_answers_qaset_id_qasets", "answers", "qasets", "CASCADE"),
        ("fk_projects_base_language_id_languages", "projects", "languages", "RESTRICT"),
        ("fk_protocols_project_id_projects", "protocols", "projects", "RESTRICT"),
        ("fk_qasets_theme_id_themes", "qasets", "themes", "RESTRICT"),
        (
            "fk_question_variants_language_id_languages",
            "question_variants",
            "languages",
            "RESTRICT",
        ),
        ("fk_question_variants_qaset_id_answers", "question_variants", "answers", "CASCADE"),
        ("fk_question_variants_qaset_id_qasets", "question_variants", "qasets", "CASCADE"),
        ("fk_themes_protocol_id_protocols", "themes", "protocols", "RESTRICT"),
        ("fk_variant_intents_intent_id_intents", "variant_intents", "intents", "RESTRICT"),
        (
            "fk_variant_intents_variant_id_question_variants",
            "variant_intents",
            "question_variants",
            "CASCADE",
        ),
        (
            "fk_variant_translation_links_qaset_id_qasets",
            "variant_translation_links",
            "qasets",
            "CASCADE",
        ),
        (
            "fk_variant_translation_links_variant_high_id_question_variants",
            "variant_translation_links",
            "question_variants",
            "CASCADE",
        ),
        (
            "fk_variant_translation_links_variant_low_id_question_variants",
            "variant_translation_links",
            "question_variants",
            "CASCADE",
        ),
    ]
    link_constraints = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' AND table_name LIKE '%translation_links' "
            "AND constraint_type IN ('UNIQUE', 'CHECK') AND constraint_name NOT LIKE '%not_null' "
            "ORDER BY constraint_name",
        )
    )
    assert link_constraints == [
        ("ck_answer_translation_links_canonical_pair", "CHECK"),
        ("ck_variant_translation_links_canonical_pair", "CHECK"),
        ("uq_answer_translation_links_pair", "UNIQUE"),
        ("uq_variant_translation_links_pair", "UNIQUE"),
    ]
    intent_constraints = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' AND table_name IN ('intents', 'variant_intents') "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE') ORDER BY constraint_name",
        )
    )
    assert intent_constraints == [
        ("pk_intents", "PRIMARY KEY"),
        ("pk_variant_intents", "PRIMARY KEY"),
        ("uq_intents_key", "UNIQUE"),
    ]
    unique = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' AND table_name = 'answers' "
            "AND constraint_type = 'UNIQUE'",
        )
    )
    assert unique == [("uq_answers_qaset_id_language_id",)]
    indexes = asyncio.run(
        _query(
            postgres_url,
            f"SELECT indexname FROM pg_indexes WHERE schemaname = '{SCHEMA}' "
            "AND indexname LIKE 'ix_%' ORDER BY indexname",
        )
    )
    assert indexes == [
        ("ix_answer_translation_links_answer_high_id",),
        ("ix_answer_translation_links_answer_low_id",),
        ("ix_answers_language_id",),
        ("ix_projects_base_language_id",),
        ("ix_protocols_project_id",),
        ("ix_qasets_theme_id",),
        ("ix_question_variants_language_id",),
        ("ix_question_variants_qaset_id_language_id",),
        ("ix_themes_protocol_id",),
        ("ix_variant_intents_intent_id",),
        ("ix_variant_intents_variant_id",),
        ("ix_variant_translation_links_variant_high_id",),
        ("ix_variant_translation_links_variant_low_id",),
    ]

    created_at = asyncio.run(
        _query(
            postgres_url,
            "SELECT table_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            f"WHERE table_schema = '{SCHEMA}' AND column_name = 'created_at' ORDER BY table_name",
        )
    )
    assert created_at == [
        (table, "timestamp with time zone", "NO", "now()")
        for table in (
            "answer_translation_links",
            "answers",
            "question_variants",
            "variant_intents",
            "variant_translation_links",
        )
    ]
    command.downgrade(_alembic_config(), "0004_qasets")
    assert (
        asyncio.run(
            _query(
                postgres_url,
                "SELECT 1 FROM information_schema.columns "
                f"WHERE table_schema = '{SCHEMA}' AND (column_name = 'created_at' "
                "OR table_name LIKE '%translation_links' OR table_name LIKE '%intents')",
            )
        )
        == []
    )
    command.upgrade(_alembic_config(), "head")

    # Idempotent: a second upgrade is a no-op, and every revision downgrades cleanly.
    command.upgrade(_alembic_config(), "head")
    command.downgrade(_alembic_config(), "0002_languages")
    remaining = asyncio.run(
        _query(
            postgres_url,
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{SCHEMA}' "
            "AND table_name <> 'alembic_version' ORDER BY table_name",
        )
    )
    assert remaining == [("languages",)]
    command.downgrade(_alembic_config(), "base")
    tables = asyncio.run(
        _query(
            postgres_url,
            f"SELECT 1 FROM information_schema.tables WHERE table_schema = '{SCHEMA}' "
            "AND table_name <> 'alembic_version'",
        )
    )
    assert tables == []
    assert (
        asyncio.run(_query(postgres_url, f"SELECT version_num FROM {SCHEMA}.alembic_version")) == []
    )
