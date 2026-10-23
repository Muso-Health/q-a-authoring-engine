from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.settings import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    """A Settings read from exactly ``env`` (QA_AUTHORING_-prefixed), never a stray .env file."""
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_defaults_select_the_local_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.use_cloud_sql_connector is False
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_database_url_is_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://u:p@db.example:6543/qa"
    settings = _settings(monkeypatch, DATABASE_URL=url)
    assert settings.database_url == url
    assert settings.use_cloud_sql_connector is False


def test_instance_connection_name_selects_the_cloud_sql_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        DB_INSTANCE_CONNECTION_NAME="proj:region:inst",
        DB_USER="qa_app",
        DB_PASSWORD="secret",
        DB_NAME="qa_authoring",
        DB_IP_TYPE="private",
    )
    assert settings.use_cloud_sql_connector is True
    assert settings.db_instance_connection_name == "proj:region:inst"
    assert settings.db_user == "qa_app"
    assert settings.db_password == "secret"
    assert settings.db_name == "qa_authoring"
    assert settings.db_ip_type == "private"


def test_unprefixed_env_vars_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_INSTANCE_CONNECTION_NAME", "proj:region:inst")
    monkeypatch.setenv("BUDGETING_DB_INSTANCE_CONNECTION_NAME", "proj:region:inst")
    assert _settings(monkeypatch).use_cloud_sql_connector is False


def test_schema_name_defaults_to_the_app_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _settings(monkeypatch).db_schema == "qa_authoring"


def test_schema_name_is_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _settings(monkeypatch, DB_SCHEMA="qa_authoring_test").db_schema == "qa_authoring_test"


@pytest.mark.parametrize("bad", ["", "public", "Qa", "qa-authoring", 'qa"; drop', "1qa"])
def test_schema_name_must_be_a_plain_identifier_other_than_public(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    """The schema is interpolated into DDL and search_path, and isolation forbids sharing
    ``public`` with other apps' tables — reject anything that is not a plain lowercase name."""
    with pytest.raises(ValidationError):
        _settings(monkeypatch, DB_SCHEMA=bad)


def test_cors_origins_are_split_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        CORS_ALLOWED_ORIGINS=" http://localhost:4200, https://qa.example.org ,,",
    )
    assert settings.cors_origins == ["http://localhost:4200", "https://qa.example.org"]


def test_cors_origins_default_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _settings(monkeypatch).cors_origins == []
