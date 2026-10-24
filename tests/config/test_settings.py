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
    monkeypatch.setenv("OTHER_DB_INSTANCE_CONNECTION_NAME", "proj:region:inst")
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


def test_audio_settings_are_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        AUDIO_STORAGE_BACKEND="gcs",
        AUDIO_BUCKET="qa-audio",
        AUDIO_OBJECT_PREFIX="recordings/",
        AUDIO_PLAYBACK_URL_TTL_SECONDS="120",
        AUDIO_MAX_UPLOAD_BYTES="2048",
        AUDIO_ALLOWED_MIME_TYPES=" audio/webm, audio/ogg ,,",
        AUDIO_FFPROBE_PATH="/usr/bin/ffprobe",
    )
    assert settings.audio_storage_backend == "gcs"
    assert settings.audio_bucket == "qa-audio"
    assert settings.audio_object_prefix == "recordings/"
    assert settings.audio_playback_url_ttl_seconds == 120
    assert settings.audio_max_upload_bytes == 2048
    assert settings.audio_mime_types == frozenset({"audio/webm", "audio/ogg"})
    assert settings.audio_ffprobe_path == "/usr/bin/ffprobe"


def test_audio_defaults_store_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.audio_storage_backend == "local"
    assert "audio/webm" in settings.audio_mime_types


@pytest.mark.parametrize("backend", ["s3", "", "GCS"])
def test_audio_backend_must_be_known(monkeypatch: pytest.MonkeyPatch, backend: str) -> None:
    with pytest.raises(ValidationError):
        _settings(monkeypatch, AUDIO_STORAGE_BACKEND=backend)


def test_auth_defaults_to_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QA_AUTHORING_AUTH_PROVIDER", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (settings.auth_provider, settings.auth_entra_audience, settings.auth_entra_tenant) == (
        "entra",
        "",
        "",
    )
    settings = _settings(monkeypatch, AUTH_ENTRA_AUDIENCE="api://qa", AUTH_ENTRA_TENANT="t-id")
    assert (settings.auth_entra_audience, settings.auth_entra_tenant) == ("api://qa", "t-id")


def test_dev_auth_and_bootstrap_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, AUTH_PROVIDER="dev", BOOTSTRAP_ADMIN_EMAIL="root@example.org")
    assert (settings.auth_provider, settings.bootstrap_admin_email) == ("dev", "root@example.org")


@pytest.mark.parametrize("provider", ["", "iap", "oauth", "DEV", "ENTRA"])
def test_auth_provider_must_be_known(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    with pytest.raises(ValidationError):
        _settings(monkeypatch, AUTH_PROVIDER=provider)


def test_llm_and_translation_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    defaults = _settings(monkeypatch)
    assert (defaults.llm_provider, defaults.llm_model) == ("gemini", "gemini-2.5-flash")
    settings = _settings(
        monkeypatch,
        LLM_MODEL="gemini-2.5-pro",
        LLM_PROJECT="proj",
        LLM_LOCATION="europe-west1",
        LLM_API_KEY="key",
        LLM_TIMEOUT_SECONDS="12.5",
        GOOGLE_TRANSLATE_PROJECT="translate-proj",
        GOOGLE_TRANSLATE_LOCATION="us-central1",
    )
    assert (settings.llm_model, settings.llm_project, settings.llm_location) == (
        "gemini-2.5-pro",
        "proj",
        "europe-west1",
    )
    assert (settings.llm_api_key, settings.llm_timeout_seconds) == ("key", 12.5)
    assert (settings.google_translate_project, settings.google_translate_location) == (
        "translate-proj",
        "us-central1",
    )


@pytest.mark.parametrize("provider", ["", "openai", "GEMINI"])
def test_llm_provider_must_be_known(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    with pytest.raises(ValidationError):
        _settings(monkeypatch, LLM_PROVIDER=provider)
