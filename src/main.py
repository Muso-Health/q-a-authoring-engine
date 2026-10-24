from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING

from apps.api.app import create_app
from config.audio import (
    audio_policy_from_settings,
    audio_probe_from_settings,
    audio_storage_from_settings,
)
from config.auth import identity_provider_from_settings
from config.container import Container
from config.database import engine_factory_from_settings
from config.documentation import (
    documentation_policy_from_settings,
    documentation_storage_from_settings,
)
from config.llm import google_translator_from_settings, llm_from_settings
from config.settings import Settings
from qa_authoring.application.bootstrap_admin.command import BootstrapAdminCommand
from qa_authoring.application.seed_prompt_templates.command import SeedPromptTemplatesCommand
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

# Composition root (``uvicorn main:app``). Settings pick the engine factory; the engine itself is
# created in the lifespan, on uvicorn's serving loop — required for the Cloud SQL Connector, and
# harmless for the local DSN — and disposed on shutdown.
_settings = Settings()
_engine_factory = engine_factory_from_settings(_settings)
_audio_storage = audio_storage_from_settings(_settings)
_audio_probe = audio_probe_from_settings(_settings)
_audio_policy = audio_policy_from_settings(_settings)
_identity_provider = identity_provider_from_settings(_settings)
_llm = llm_from_settings(_settings)
_google_translator = google_translator_from_settings(_settings)
_documentation_storage = documentation_storage_from_settings(_settings)
_documentation_policy = documentation_policy_from_settings(_settings)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with _engine_factory.engine() as engine:
        container = Container(
            partial(SqlAlchemyUnitOfWork, engine),
            audio_storage=_audio_storage,
            audio_probe=_audio_probe,
            audio_policy=_audio_policy,
            llm=_llm,
            google_translator=_google_translator,
            documentation_storage=_documentation_storage,
            documentation_policy=_documentation_policy,
        )
        await container.run(container.build_seed_prompt_templates, SeedPromptTemplatesCommand())
        if _settings.bootstrap_admin_email:
            command = BootstrapAdminCommand(_settings.bootstrap_admin_email)
            await container.run(container.build_bootstrap_admin, command)
        app.state.container = container
        yield


app = create_app(
    identity_provider=_identity_provider,
    cors_allowed_origins=_settings.cors_origins,
    lifespan=_lifespan,
)
