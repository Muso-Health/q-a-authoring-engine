from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request

from apps.api.dependencies import get_container
from qa_authoring.application.access_errors import PermissionDeniedError
from qa_authoring.application.access_response import (
    CurrentUserResult,
)
from qa_authoring.application.audio_errors import AudioNotFoundError
from qa_authoring.application.documentation_errors import DocumentationNotFoundError
from qa_authoring.application.ports.identity import UnauthenticatedError
from qa_authoring.application.ports.resource_scopes import ResourceKind, ResourceScope
from qa_authoring.application.project_errors import ProjectNotFoundError
from qa_authoring.application.protocol_errors import ProtocolNotFoundError
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.application.resolve_current_user.command import ResolveCurrentUserQuery
from qa_authoring.application.resolve_resource_scope.command import ResolveResourceScopeQuery
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.permission import Permission, PermissionScope


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


def _resource_id(request: Request, kind: ResourceKind) -> UUID | None:
    """The ``{<kind>_id}`` path parameter; None when malformed (the route then answers 422)."""
    try:
        return UUID(str(request.path_params[f"{kind.value}_id"]))
    except (KeyError, ValueError):
        return None


async def _scope(request: Request, kind: ResourceKind, resource_id: UUID) -> ResourceScope | None:
    container = get_container(request)
    query = ResolveResourceScopeQuery(kind, resource_id)
    return await container.run(container.build_resolve_resource_scope, query)


class PermissionGuard:
    """Lets the request through only if the current user holds ``permission`` — within the
    project (and language) of the ``on`` resource of the path, for a scoped permission. A
    resource that does not exist is left to the route, which answers 404."""

    def __init__(self, permission: Permission, on: ResourceKind | None = None) -> None:
        self.permission = permission
        self.on = on

    async def __call__(self, request: Request, user: CurrentUser) -> CurrentUserResult:
        if not user.holds(self.permission):
            raise PermissionDeniedError(self.permission)
        if (
            self.on is None
            or self.permission.scope is PermissionScope.GLOBAL
            or user.authorize(self.permission)
        ):
            return user
        resource_id = _resource_id(request, self.on)
        scope = None if resource_id is None else await _scope(request, self.on, resource_id)
        if scope is not None and not user.authorize(
            self.permission, scope.project_id, scope.language_id
        ):
            raise PermissionDeniedError(self.permission)
        return user


def requires(permission: Permission, on: ResourceKind | None = None) -> Any:
    """``dependencies=[requires(Permission.X, on=ResourceKind.Y)]`` on a route or router."""
    return Depends(PermissionGuard(permission, on))


_NOT_FOUND = {
    ResourceKind.PROJECT: ProjectNotFoundError,
    ResourceKind.PROTOCOL: ProtocolNotFoundError,
    ResourceKind.THEME: ThemeNotFoundError,
    ResourceKind.QASET: QASetNotFoundError,
    ResourceKind.AUDIO: AudioNotFoundError,
    ResourceKind.DOCUMENTATION: DocumentationNotFoundError,
}


class VisibilityGuard:
    """A read of a resource whose project the user cannot see answers the resource's own 404,
    so its existence does not leak."""

    def __init__(self, kind: ResourceKind) -> None:
        self.kind = kind

    async def __call__(self, request: Request, user: CurrentUser) -> CurrentUserResult:
        if user.authorization.visible_project_ids is None:
            return user
        resource_id = _resource_id(request, self.kind)
        if resource_id is None:
            return user
        scope = await _scope(request, self.kind, resource_id)
        if scope is not None and not user.can_see(scope.project_id):
            raise _NOT_FOUND[self.kind](resource_id)
        return user


def visible(kind: ResourceKind) -> Any:
    """``dependencies=[visible(ResourceKind.Y)]`` on a read of the ``{<kind>_id}`` resource."""
    return Depends(VisibilityGuard(kind))
