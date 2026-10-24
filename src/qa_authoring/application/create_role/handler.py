from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import RoleResult
from qa_authoring.application.role_errors import RoleNameExistsError
from qa_authoring.domain.model.permission import parse_permissions
from qa_authoring.domain.model.role import Role

if TYPE_CHECKING:
    from qa_authoring.application.create_role.command import CreateRoleCommand
    from qa_authoring.application.ports.role_repository import RoleRepository


class CreateRoleHandler:
    """Create a role over codes of the fixed permission catalogue; unknown codes are refused."""

    def __init__(self, roles: RoleRepository) -> None:
        self._roles = roles

    async def __call__(self, command: CreateRoleCommand) -> RoleResult:
        role = Role.create(
            name=command.name, permissions=parse_permissions(command.permission_codes)
        )
        if await self._roles.find_by_key(role.key) is not None:
            raise RoleNameExistsError(role.name)
        await self._roles.add(role)
        return RoleResult.of(role)
