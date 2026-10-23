from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from qa_authoring.infrastructure.persistence.engine import (
    CloudSqlEngineFactory,
    EngineFactory,
    LocalDsnEngineFactory,
)


def test_both_factories_satisfy_the_port() -> None:
    local: EngineFactory = LocalDsnEngineFactory(
        database_url="postgresql+asyncpg://u:p@localhost/qa", schema="qa_authoring"
    )
    cloud: EngineFactory = CloudSqlEngineFactory(
        instance_connection_name="p:r:i", user="u", password="pw", db="qa", schema="qa_authoring"
    )
    assert isinstance(local, EngineFactory)
    assert isinstance(cloud, EngineFactory)


async def test_local_factory_pins_the_search_path_to_the_app_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def spy(url: str, **kwargs: Any) -> Any:
        captured["url"] = url
        captured.update(kwargs)
        return create_async_engine(url, **kwargs)

    monkeypatch.setattr("qa_authoring.infrastructure.persistence.engine.create_async_engine", spy)
    factory = LocalDsnEngineFactory(
        database_url="postgresql+asyncpg://u:p@localhost/qa", schema="qa_x", pool_size=2
    )
    async with factory.engine() as engine:
        assert engine is not None  # lazy: nothing connects until first use

    assert captured["url"] == "postgresql+asyncpg://u:p@localhost/qa"
    assert captured["connect_args"] == {"server_settings": {"search_path": "qa_x"}}
    assert captured["pool_size"] == 2
    assert captured["pool_pre_ping"] is True


async def test_cloud_sql_factory_binds_the_connector_to_the_running_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Connector binds to the loop it is created on, so it must be created INSIDE the serving
    loop (via create_async_connector, lazy refresh for Cloud Run) and closed on exit. Each pooled
    connection is dialled with the schema pinned as search_path."""
    connector_pkg = pytest.importorskip("google.cloud.sql.connector")
    seen: dict[str, Any] = {}

    class FakeConnector:
        async def connect_async(self, *args: Any, **kwargs: Any) -> Any:
            seen["connect_args"] = args
            seen["connect_kwargs"] = kwargs
            raise RuntimeError("stop before a real dial")

        async def close_async(self) -> None:
            seen["closed"] = True

    async def fake_create_async_connector(**kwargs: Any) -> FakeConnector:
        seen["loop"] = asyncio.get_running_loop()
        seen["refresh_strategy"] = kwargs.get("refresh_strategy")
        return FakeConnector()

    monkeypatch.setattr(connector_pkg, "create_async_connector", fake_create_async_connector)

    factory = CloudSqlEngineFactory(
        instance_connection_name="proj:region:inst",
        user="u",
        password="pw",
        db="qa",
        schema="qa_x",
        ip_type="private",
    )
    running = asyncio.get_running_loop()
    async with factory.engine() as engine:
        assert seen["loop"] is running
        assert seen["refresh_strategy"] == "lazy"
        with pytest.raises(RuntimeError, match="stop before a real dial"):
            async with engine.connect():
                pass

    assert seen["connect_args"] == ("proj:region:inst", "asyncpg")
    kwargs = seen["connect_kwargs"]
    assert kwargs["user"] == "u"
    assert kwargs["password"] == "pw"
    assert kwargs["db"] == "qa"
    assert kwargs["ip_type"] == connector_pkg.IPTypes.PRIVATE
    assert kwargs["server_settings"] == {"search_path": "qa_x"}
    assert seen.get("closed") is True
