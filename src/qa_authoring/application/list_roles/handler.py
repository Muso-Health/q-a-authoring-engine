from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import RoleResult

if TYPE_CHECKING:
    from qa_authoring.application.list_roles.command import ListRolesQuery
    from qa_authoring.application.ports.role_repository import RoleRepository


class ListRolesHandler:
    def __init__(self, roles: RoleRepository) -> None:
        self._roles = roles

    async def __call__(self, query: ListRolesQuery) -> tuple[RoleResult, ...]:
        return tuple(RoleResult.of(role) for role in await self._roles.list())
