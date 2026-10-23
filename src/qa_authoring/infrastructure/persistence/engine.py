from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from contextlib import AbstractAsyncContextManager

    from sqlalchemy.ext.asyncio import AsyncEngine


@runtime_checkable
class EngineFactory(Protocol):
    """The port every caller (``main.py``, Alembic's env) goes through to get an engine.

    ``engine()`` is an async context manager entered ON the serving event loop: it builds the engine
    (and whatever it needs, e.g. a Cloud SQL Connector) and disposes all of it on exit. Swapping the
    connection strategy means passing a different factory — callers never change.
    """

    @property
    def schema(self) -> str: ...

    def engine(self) -> AbstractAsyncContextManager[AsyncEngine]: ...


def _search_path(schema: str) -> dict[str, str]:
    # Pinned per connection so unqualified tables resolve to the app's own schema only.
    return {"search_path": schema}


@dataclass(frozen=True)
class LocalDsnEngineFactory:
    """Local dev and tests: a plain asyncpg URL (localhost, docker compose, a testcontainer)."""

    database_url: str
    schema: str
    pool_size: int = 5

    @asynccontextmanager
    async def engine(self) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(
            self.database_url,
            connect_args={"server_settings": _search_path(self.schema)},
            pool_size=self.pool_size,
            pool_pre_ping=True,
        )
        try:
            yield engine
        finally:
            await engine.dispose()


@dataclass(frozen=True)
class CloudSqlEngineFactory:
    """Production: dialled through the Cloud SQL Python Connector.

    A Connector binds to the loop it is created on and refuses ``connect_async()`` from any other
    loop (``ConnectorLoopError``), so it is created inside ``engine()`` — never at import scope.
    Lazy refresh: Cloud Run throttles CPU outside a request, so the ephemeral certificate is
    refreshed on the request that needs it rather than by a background task that would stall.
    """

    instance_connection_name: str
    user: str
    password: str
    db: str
    schema: str
    ip_type: str = "public"
    pool_size: int = 5

    @asynccontextmanager
    async def engine(self) -> AsyncIterator[AsyncEngine]:
        from google.cloud.sql.connector import IPTypes, create_async_connector

        resolved_ip = IPTypes.PRIVATE if self.ip_type.lower() == "private" else IPTypes.PUBLIC
        connector = await create_async_connector(refresh_strategy="lazy")

        async def getconn() -> Any:
            return await connector.connect_async(
                self.instance_connection_name,
                "asyncpg",
                user=self.user,
                password=self.password,
                db=self.db,
                ip_type=resolved_ip,
                server_settings=_search_path(self.schema),
            )

        engine = create_async_engine(
            "postgresql+asyncpg://",
            async_creator=getconn,
            pool_size=self.pool_size,
            pool_pre_ping=True,
        )
        try:
            yield engine
        finally:
            await engine.dispose()
            await connector.close_async()
