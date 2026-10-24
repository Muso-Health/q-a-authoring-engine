from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_role
from qa_authoring.application.access_response import RoleResult
from qa_authoring.application.role_errors import RoleNameExistsError
from qa_authoring.domain.model.permission import parse_permissions

if TYPE_CHECKING:
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.update_role.command import UpdateRoleCommand


class UpdateRoleHandler:
    def __init__(self, roles: RoleRepository) -> None:
        self._roles = roles

    async def __call__(self, command: UpdateRoleCommand) -> RoleResult:
        role = await load_role(self._roles, command.role_id)
        if command.permission_codes is not None:
            role.replace_permissions(parse_permissions(command.permission_codes))
        if command.name is not None:
            role.rename(command.name)
            clash = await self._roles.find_by_key(role.key)
            if clash is not None and clash.id != role.id:
                raise RoleNameExistsError(role.name)
        await self._roles.update(role)
        return RoleResult.of(role)
