from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_role
from qa_authoring.application.access_response import RoleResult

if TYPE_CHECKING:
    from qa_authoring.application.get_role.command import GetRoleQuery
    from qa_authoring.application.ports.role_repository import RoleRepository


class GetRoleHandler:
    def __init__(self, roles: RoleRepository) -> None:
        self._roles = roles

    async def __call__(self, query: GetRoleQuery) -> RoleResult:
        return RoleResult.of(await load_role(self._roles, query.role_id))
