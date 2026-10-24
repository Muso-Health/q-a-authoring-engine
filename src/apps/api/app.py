from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.auth import require_authenticated
from apps.api.errors import register_error_handlers
from apps.api.routers.access import router as access_router
from apps.api.routers.audio import router as audio_router
from apps.api.routers.categories import router as categories_router
from apps.api.routers.generation import router as generation_router
from apps.api.routers.health import router as health_router
from apps.api.routers.intents import router as intents_router
from apps.api.routers.languages import router as languages_router
from apps.api.routers.projects import router as projects_router
from apps.api.routers.prompt_templates import router as prompt_templates_router
from apps.api.routers.protocols import router as protocols_router
from apps.api.routers.qasets import router as qasets_router
from apps.api.routers.roles import router as roles_router
from apps.api.routers.themes import router as themes_router
from apps.api.routers.translation import router as translation_router
from apps.api.routers.users import router as users_router
from apps.api.routers.validations import router as validations_router
from apps.api.version import API_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.types import Lifespan

    from config.container import Container
    from qa_authoring.application.ports.identity import IdentityProvider


def create_app(
    *,
    container: Container | None = None,
    identity_provider: IdentityProvider | None = None,
    cors_allowed_origins: Sequence[str] = (),
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    """Assemble the ASGI app over an already-built container (or one a lifespan supplies).

    A factory, not a module-level app, so a test builds it over fakes — no network, no globals.
    ``container`` may be omitted when a ``lifespan`` sets ``app.state.container`` on startup — the
    path ``main.py`` takes, because the engine (and a Cloud SQL Connector) must be created on the
    serving event loop. ``cors_allowed_origins`` (the Angular SPA's origins) turns on CORS when
    non-empty.

    Every route but ``/health`` requires an authenticated, active user (from
    ``identity_provider``; none means every such request is unauthenticated); writes also
    require their permission, declared on the route.
    """
    app = FastAPI(title="Muso Q&A Authoring Engine API", version=API_VERSION, lifespan=lifespan)
    if container is not None:
        app.state.container = container
    app.state.identity_provider = identity_provider
    if cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )
    register_error_handlers(app)
    app.include_router(health_router)
    for router in (
        access_router,
        users_router,
        roles_router,
        languages_router,
        projects_router,
        protocols_router,
        themes_router,
        qasets_router,
        intents_router,
        categories_router,
        audio_router,
        validations_router,
        prompt_templates_router,
        translation_router,
        generation_router,
    ):
        app.include_router(router, dependencies=[Depends(require_authenticated)])
    return app
