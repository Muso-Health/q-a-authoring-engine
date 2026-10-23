from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers.health import router as health_router
from apps.api.version import API_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.types import Lifespan

    from config.container import Container


def create_app(
    *,
    container: Container | None = None,
    cors_allowed_origins: Sequence[str] = (),
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    """Assemble the ASGI app over an already-built container (or one a lifespan supplies).

    A factory, not a module-level app, so a test builds it over fakes — no network, no globals.
    ``container`` may be omitted when a ``lifespan`` sets ``app.state.container`` on startup — the
    path ``main.py`` takes, because the engine (and a Cloud SQL Connector) must be created on the
    serving event loop. ``cors_allowed_origins`` (the Angular SPA's origins) turns on CORS when
    non-empty.
    """
    app = FastAPI(title="Muso Q&A Authoring Engine API", version=API_VERSION, lifespan=lifespan)
    if container is not None:
        app.state.container = container
    if cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )
    app.include_router(health_router)
    return app
