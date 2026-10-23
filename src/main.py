from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING

from apps.api.app import create_app
from config.container import Container
from config.database import engine_factory_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

# Composition root (``uvicorn main:app``). Settings pick the engine factory; the engine itself is
# created in the lifespan, on uvicorn's serving loop — required for the Cloud SQL Connector, and
# harmless for the local DSN — and disposed on shutdown.
_settings = Settings()
_engine_factory = engine_factory_from_settings(_settings)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with _engine_factory.engine() as engine:
        app.state.container = Container(partial(SqlAlchemyUnitOfWork, engine))
        yield


app = create_app(cors_allowed_origins=_settings.cors_origins, lifespan=_lifespan)
