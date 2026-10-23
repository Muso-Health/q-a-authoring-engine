from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from apps.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI


def test_cors_allows_configured_origins_only() -> None:
    app = create_app(cors_allowed_origins=["http://localhost:4200"])
    with TestClient(app) as client:
        allowed = client.get("/health", headers={"Origin": "http://localhost:4200"})
        other = client.get("/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4200"
    assert "access-control-allow-origin" not in other.headers


def test_no_cors_headers_when_no_origins_are_configured() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:4200"})
    assert "access-control-allow-origin" not in response.headers


def test_create_app_defers_the_container_to_the_lifespan() -> None:
    """The engine (and a Cloud SQL Connector) must be created on the serving loop, so main.py
    builds the container in a lifespan; create_app itself never builds one."""
    sentinel = object()
    torn_down: dict[str, bool] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = sentinel
        yield
        torn_down["yes"] = True

    app = create_app(lifespan=lifespan)
    assert not hasattr(app.state, "container")
    with TestClient(app):
        assert app.state.container is sentinel
    assert torn_down["yes"] is True
