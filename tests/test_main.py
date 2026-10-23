from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

if TYPE_CHECKING:
    import pytest


def test_entrypoint_exposes_an_app_that_serves_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """``uvicorn main:app`` is the entrypoint. The engine is lazy, so
    startup builds the container without dialling the (unreachable) database."""
    monkeypatch.setenv("QA_AUTHORING_DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/none")
    main = importlib.import_module("main")

    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert main.app.state.container is not None
