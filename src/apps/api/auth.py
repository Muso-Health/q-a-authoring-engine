from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from apps.api.dependencies import get_container
from qa_authoring.application.access_errors import PermissionDeniedError
from qa_authoring.application.access_response import (
    CurrentUserResult,
)
from qa_authoring.application.ports.identity import UnauthenticatedError
from qa_authoring.application.resolve_current_user.command import ResolveCurrentUserQuery
from qa_authoring.domain.model.permission import Permission  # noqa: TC001 — resolved at runtime


async def current_user(request: Request) -> CurrentUserResult:
    """The caller, authenticated by the configured identity provider and mapped to an active
    user. Resolved once per request (FastAPI caches it across the guards that need it)."""
    provider = getattr(request.app.state, "identity_provider", None)
    if provider is None:
        raise UnauthenticatedError("no identity provider is configured")
    identity = await provider.identify(request.headers)
    container = get_container(request)
    query = ResolveCurrentUserQuery(identity)
    return await container.run(container.build_resolve_current_user, query)


CurrentUser = Annotated[CurrentUserResult, Depends(current_user)]


async def require_authenticated(user: CurrentUser) -> CurrentUserResult:
    return user


class PermissionGuard:
    """Lets the request through only if the current user holds ``permission``."""

    def __init__(self, permission: Permission) -> None:
        self.permission = permission

    async def __call__(self, user: CurrentUser) -> CurrentUserResult:
        if not user.holds(self.permission):
            raise PermissionDeniedError(self.permission)
        return user


def requires(permission: Permission) -> Any:
    """``dependencies=[requires(Permission.X)]`` on a route or router."""
    return Depends(PermissionGuard(permission))
