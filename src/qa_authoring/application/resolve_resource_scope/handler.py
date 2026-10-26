from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qa_authoring.application.ports.resource_scopes import ResourceScope, ResourceScopes
    from qa_authoring.application.resolve_resource_scope.command import ResolveResourceScopeQuery


class ResolveResourceScopeHandler:
    """The project (and language) a resource belongs to, to authorize an action on it."""

    def __init__(self, scopes: ResourceScopes) -> None:
        self._scopes = scopes

    async def __call__(self, query: ResolveResourceScopeQuery) -> ResourceScope | None:
        return await self._scopes.resolve(query.kind, query.resource_id)
