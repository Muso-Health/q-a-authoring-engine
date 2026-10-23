from __future__ import annotations

from typing import TYPE_CHECKING

from config.database import engine_factory_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.persistence.engine import (
    CloudSqlEngineFactory,
    LocalDsnEngineFactory,
)

if TYPE_CHECKING:
    import pytest


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_local_dsn_factory_is_selected_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://u:p@localhost:5432/qa"
    factory = engine_factory_from_settings(
        _settings(monkeypatch, DATABASE_URL=url, DB_SCHEMA="qa_x", DB_POOL_SIZE="3")
    )
    assert isinstance(factory, LocalDsnEngineFactory)
    assert factory.database_url == url
    assert factory.schema == "qa_x"
    assert factory.pool_size == 3


def test_cloud_sql_factory_is_selected_when_an_instance_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = engine_factory_from_settings(
        _settings(
            monkeypatch,
            DB_INSTANCE_CONNECTION_NAME="proj:region:inst",
            DB_USER="qa_app",
            DB_PASSWORD="pw",
            DB_NAME="qa",
            DB_IP_TYPE="private",
            DB_SCHEMA="qa_x",
        )
    )
    assert isinstance(factory, CloudSqlEngineFactory)
    assert factory.instance_connection_name == "proj:region:inst"
    assert factory.user == "qa_app"
    assert factory.password == "pw"
    assert factory.db == "qa"
    assert factory.ip_type == "private"
    assert factory.schema == "qa_x"
