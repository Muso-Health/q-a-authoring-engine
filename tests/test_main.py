from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from qa_authoring.domain.model.prompt_template import DEFAULT_TEMPLATES, PromptTemplateKey
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.conftest import REPO_SCHEMA

if TYPE_CHECKING:
    from types import ModuleType

    from sqlalchemy.ext.asyncio import AsyncEngine


def _fresh_main(monkeypatch: pytest.MonkeyPatch, database_url: str, schema: str) -> ModuleType:
    """``uvicorn main:app``, imported anew so it reads the environment set here."""
    monkeypatch.setenv("QA_AUTHORING_DATABASE_URL", database_url)
    monkeypatch.setenv("QA_AUTHORING_DB_SCHEMA", schema)
    monkeypatch.setenv("QA_AUTHORING_AUTH_PROVIDER", "dev")
    monkeypatch.delenv("QA_AUTHORING_BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delitem(sys.modules, "main", raising=False)
    return importlib.import_module("main")


def test_entrypoint_exposes_an_app_that_serves_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing the entrypoint touches no database: the engine is built on startup."""
    main = _fresh_main(monkeypatch, "postgresql+asyncpg://u:p@127.0.0.1:1/none", "qa_authoring")
    assert TestClient(main.app).get("/health").json() == {"status": "ok"}


@pytest.mark.integration
async def test_startup_seeds_the_default_prompt_templates(
    monkeypatch: pytest.MonkeyPatch, migrated_url: str, migrated_engine: AsyncEngine
) -> None:
    main = _fresh_main(monkeypatch, migrated_url, REPO_SCHEMA)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert main.app.state.container is not None

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        templates = await uow.prompt_templates.list()
    assert [(t.key, t.content) for t in templates] == [
        (key, DEFAULT_TEMPLATES[key]) for key in PromptTemplateKey
    ]
