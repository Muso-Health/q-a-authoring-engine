from __future__ import annotations

import asyncio
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    PromptTemplate,
    PromptTemplateKey,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "qa_authoring_it"
# An audio's created_at is set by the domain; role assignments need per-row timestamps.
_CREATED_AT_DEFAULTS = {
    "audios": None,
    "documentation": None,
    "glossary_terms": None,
    "user_role_assignments": "clock_timestamp()",
    "question_variants": "clock_timestamp()",
}


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
    assert versions == [("0018_glossary",)]
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
        ("fk_audios_answer_id_answers", "audios", "answers", "CASCADE"),
        ("fk_audios_variant_id_question_variants", "audios", "question_variants", "CASCADE"),
        ("fk_documentation_theme_id_themes", "documentation", "themes", "CASCADE"),
        ("fk_glossary_forms_language_id_languages", "glossary_forms", "languages", "RESTRICT"),
        (
            "fk_glossary_forms_term_id_glossary_terms",
            "glossary_forms",
            "glossary_terms",
            "CASCADE",
        ),
        ("fk_projects_base_language_id_languages", "projects", "languages", "RESTRICT"),
        ("fk_prompt_templates_updated_by_users", "prompt_templates", "users", "RESTRICT"),
        ("fk_protocols_project_id_projects", "protocols", "projects", "RESTRICT"),
        (
            "fk_qaset_categories_category_id_categories",
            "qaset_categories",
            "categories",
            "RESTRICT",
        ),
        ("fk_qaset_categories_qaset_id_qasets", "qaset_categories", "qasets", "CASCADE"),
        ("fk_qasets_theme_id_themes", "qasets", "themes", "RESTRICT"),
        (
            "fk_question_variants_language_id_languages",
            "question_variants",
            "languages",
            "RESTRICT",
        ),
        ("fk_question_variants_qaset_id_answers", "question_variants", "answers", "CASCADE"),
        ("fk_question_variants_qaset_id_qasets", "question_variants", "qasets", "CASCADE"),
        ("fk_role_permissions_role_id_roles", "role_permissions", "roles", "CASCADE"),
        ("fk_themes_protocol_id_protocols", "themes", "protocols", "RESTRICT"),
        (
            "fk_user_role_assignments_language_id_languages",
            "user_role_assignments",
            "languages",
            "CASCADE",
        ),
        (
            "fk_user_role_assignments_project_id_projects",
            "user_role_assignments",
            "projects",
            "CASCADE",
        ),
        ("fk_user_role_assignments_role_id_roles", "user_role_assignments", "roles", "RESTRICT"),
        ("fk_user_role_assignments_user_id_users", "user_role_assignments", "users", "CASCADE"),
        (
            "fk_validation_events_actor_user_id_users",
            "validation_events",
            "users",
            "RESTRICT",
        ),
        (
            "fk_validation_events_validation_id_validations",
            "validation_events",
            "validations",
            "CASCADE",
        ),
        ("fk_validations_answer_id_answers", "validations", "answers", "CASCADE"),
        ("fk_validations_audio_id_audios", "validations", "audios", "CASCADE"),
        ("fk_validations_qaset_id_qasets", "validations", "qasets", "CASCADE"),
        (
            "fk_validations_variant_id_question_variants",
            "validations",
            "question_variants",
            "CASCADE",
        ),
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
            f"WHERE table_schema = '{SCHEMA}' AND table_name IN "
            "('intents', 'variant_intents', 'categories', 'qaset_categories') "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE') ORDER BY constraint_name",
        )
    )
    assert intent_constraints == [
        ("pk_categories", "PRIMARY KEY"),
        ("pk_intents", "PRIMARY KEY"),
        ("pk_qaset_categories", "PRIMARY KEY"),
        ("pk_variant_intents", "PRIMARY KEY"),
        ("uq_categories_key", "UNIQUE"),
        ("uq_intents_key", "UNIQUE"),
    ]
    audio_constraints = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' AND table_name = 'audios' "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'CHECK') "
            "AND constraint_name NOT LIKE '%not_null' ORDER BY constraint_name",
        )
    )
    assert audio_constraints == [
        ("ck_audios_exactly_one_target", "CHECK"),
        ("pk_audios", "PRIMARY KEY"),
        ("uq_audios_answer_id", "UNIQUE"),
        ("uq_audios_variant_id", "UNIQUE"),
    ]
    access_constraints = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' "
            "AND table_name IN ('users', 'roles', 'role_permissions', 'user_role_assignments') "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE') ORDER BY constraint_name",
        )
    )
    assert access_constraints == [
        ("pk_role_permissions", "PRIMARY KEY"),
        ("pk_roles", "PRIMARY KEY"),
        ("pk_user_role_assignments", "PRIMARY KEY"),
        ("pk_users", "PRIMARY KEY"),
        ("uq_roles_key", "UNIQUE"),
    ]
    user_indexes = asyncio.run(
        _query(
            postgres_url,
            f"SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = '{SCHEMA}' "
            "AND tablename = 'users' AND indexname LIKE 'uq_%' ORDER BY indexname",
        )
    )
    assert [name for name, _ in user_indexes] == ["uq_users_email_lower", "uq_users_subject"]
    assert "lower(email)" in str(user_indexes[0][1])
    assert "WHERE (subject IS NOT NULL)" in str(user_indexes[1][1])
    assignment_indexes = asyncio.run(
        _query(
            postgres_url,
            f"SELECT indexdef FROM pg_indexes WHERE schemaname = '{SCHEMA}' "
            "AND indexname = 'uq_user_role_assignments_scope'",
        )
    )
    [(scope_index,)] = assignment_indexes
    assert "UNIQUE" in str(scope_index)
    assert "COALESCE(project_id" in str(scope_index)
    assert "COALESCE(language_id" in str(scope_index)
    validation_constraints = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' "
            "AND table_name IN ('validations', 'validation_events') "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'CHECK') "
            "AND constraint_name NOT LIKE '%not_null' ORDER BY constraint_name",
        )
    )
    assert validation_constraints == [
        ("ck_validation_events_states", "CHECK"),
        ("ck_validations_current_state", "CHECK"),
        ("ck_validations_subject_matches_kind", "CHECK"),
        ("pk_validation_events", "PRIMARY KEY"),
        ("pk_validations", "PRIMARY KEY"),
        ("uq_validation_events_validation_id_sequence", "UNIQUE"),
        ("uq_validations_answer_id", "UNIQUE"),
        ("uq_validations_audio_id", "UNIQUE"),
        ("uq_validations_qaset_id", "UNIQUE"),
        ("uq_validations_variant_id", "UNIQUE"),
    ]
    glossary_constraints = asyncio.run(
        _query(
            postgres_url,
            "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
            f"WHERE table_schema = '{SCHEMA}' AND table_name LIKE 'glossary_%' "
            "AND constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'CHECK') "
            "AND constraint_name NOT LIKE '%not_null' ORDER BY constraint_name",
        )
    )
    assert glossary_constraints == [
        ("ck_glossary_terms_status", "CHECK"),
        ("pk_glossary_forms", "PRIMARY KEY"),
        ("pk_glossary_terms", "PRIMARY KEY"),
        ("uq_glossary_forms_term_id_language_id", "UNIQUE"),
    ]
    glossary_indexes = {
        str(name): str(definition)
        for name, definition in asyncio.run(
            _query(
                postgres_url,
                f"SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = '{SCHEMA}' "
                "AND indexname LIKE 'ix_glossary_terms_%'",
            )
        )
    }
    # Plain indexes only: the search scans the folded search_text, needing no extension.
    assert list(glossary_indexes) == ["ix_glossary_terms_status_label"]
    assert (
        "USING btree (status, lower(label))" in glossary_indexes["ix_glossary_terms_status_label"]
    )
    extensions = asyncio.run(
        _query(postgres_url, "SELECT extname FROM pg_extension WHERE extname <> 'plpgsql'")
    )
    assert extensions == []
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
        ("ix_audios_storage_uri",),
        ("ix_documentation_storage_uri",),
        ("ix_documentation_theme_id",),
        ("ix_glossary_forms_language_id",),
        ("ix_glossary_terms_status_label",),
        ("ix_projects_base_language_id",),
        ("ix_prompt_templates_updated_by",),
        ("ix_protocols_project_id",),
        ("ix_qaset_categories_category_id",),
        ("ix_qasets_theme_id",),
        ("ix_question_variants_language_id",),
        ("ix_question_variants_qaset_id_language_id",),
        ("ix_themes_protocol_id",),
        ("ix_user_role_assignments_language_id",),
        ("ix_user_role_assignments_project_id",),
        ("ix_user_role_assignments_role_id",),
        ("ix_validation_events_actor_user_id",),
        ("ix_validations_current_state",),
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
        (table, "timestamp with time zone", "NO", _CREATED_AT_DEFAULTS.get(table, "now()"))
        for table in (
            "answer_translation_links",
            "answers",
            "audios",
            "documentation",
            "glossary_terms",
            "qaset_categories",
            "question_variants",
            "user_role_assignments",
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
                "OR table_name LIKE '%translation_links' OR table_name LIKE '%intents' "
                "OR table_name LIKE '%categories' OR table_name = 'audios' "
                "OR table_name IN ('users', 'roles', 'role_permissions', 'user_roles', "
                "'user_role_assignments', "
                "'validations', 'validation_events', 'documentation', "
                "'glossary_terms', 'glossary_forms'))",
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


def test_existing_role_assignments_become_global_and_come_back(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """0015 turns every user_roles row into a global assignment; its downgrade keeps only the
    global ones, never widening a scoped assignment."""
    schema = "qa_authoring_it_rbac"
    monkeypatch.setenv("QA_AUTHORING_DATABASE_URL", postgres_url)
    monkeypatch.setenv("QA_AUTHORING_DB_SCHEMA", schema)
    monkeypatch.delenv("QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME", raising=False)
    user, role = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    project, language = (
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444444",
    )

    async def execute(*statements: str) -> None:
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                for statement in statements:
                    await connection.execute(text(statement))
        finally:
            await engine.dispose()

    command.upgrade(_alembic_config(), "0014_documentation")
    asyncio.run(
        execute(
            f"INSERT INTO {schema}.users (id, email, display_name) "
            f"VALUES ('{user}', 'a@x.org', 'A')",
            f"INSERT INTO {schema}.roles (id, name, key) VALUES ('{role}', 'R', 'r')",
            f"INSERT INTO {schema}.user_roles (user_id, role_id) VALUES ('{user}', '{role}')",
        )
    )
    command.upgrade(_alembic_config(), "head")
    assignments = asyncio.run(
        _query(
            postgres_url,
            "SELECT user_id::text, role_id::text, project_id, language_id "
            f"FROM {schema}.user_role_assignments",
        )
    )
    assert assignments == [(user, role, None, None)]
    tables = asyncio.run(
        _query(
            postgres_url,
            "SELECT 1 FROM information_schema.tables "
            f"WHERE table_schema = '{schema}' AND table_name = 'user_roles'",
        )
    )
    assert tables == []

    asyncio.run(
        execute(
            f"INSERT INTO {schema}.languages (id, code, name) VALUES ('{language}', 'fr', 'F')",
            f"INSERT INTO {schema}.projects (id, name, base_language_id) "
            f"VALUES ('{project}', 'P', '{language}')",
            f"INSERT INTO {schema}.user_role_assignments (id, user_id, role_id, project_id) "
            f"VALUES (gen_random_uuid(), '{user}', '{role}', '{project}')",
        )
    )
    command.downgrade(_alembic_config(), "0014_documentation")
    restored = asyncio.run(
        _query(postgres_url, f"SELECT user_id::text, role_id::text FROM {schema}.user_roles")
    )
    assert restored == [(user, role)]
    command.downgrade(_alembic_config(), "base")


def test_stored_variant_prompts_gain_the_existing_questions_placeholder(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """0016: the previous default becomes the new one; an edited template gets the placeholder
    appended, so it still validates. The downgrade restores both."""
    schema = "qa_authoring_it_prompts"
    monkeypatch.setenv("QA_AUTHORING_DATABASE_URL", postgres_url)
    monkeypatch.setenv("QA_AUTHORING_DB_SCHEMA", schema)
    monkeypatch.delenv("QA_AUTHORING_DB_INSTANCE_CONNECTION_NAME", raising=False)
    spec = importlib.util.spec_from_file_location(
        "rev0016", ROOT / "migrations" / "versions" / "0016_variant_prompt_questions.py"
    )
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)

    async def store(content: str) -> None:
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f"DELETE FROM {schema}.prompt_templates"))
                await connection.execute(
                    text(
                        f"INSERT INTO {schema}.prompt_templates (key, content, updated_at) "
                        "VALUES ('variant_generation', :content, now())"
                    ),
                    {"content": content},
                )
        finally:
            await engine.dispose()

    def stored() -> str:
        [(content,)] = asyncio.run(
            _query(postgres_url, f"SELECT content FROM {schema}.prompt_templates")
        )
        return str(content)

    key = PromptTemplateKey.VARIANT_GENERATION
    edited = "Write questions in {language}.\n{context}\n{answer}"
    for before, after in (
        (revision._OLD_DEFAULT, DEFAULT_TEMPLATES[key]),
        (edited, edited + revision._SUFFIX),
    ):
        command.upgrade(_alembic_config(), "0015_scoped_role_assignments")
        asyncio.run(store(before))
        command.upgrade(_alembic_config(), "head")
        assert stored() == after
        PromptTemplate.create(key, stored(), updated_by=None, at=datetime.now(UTC))
        command.downgrade(_alembic_config(), "0015_scoped_role_assignments")
        assert stored() == before
    command.downgrade(_alembic_config(), "base")
