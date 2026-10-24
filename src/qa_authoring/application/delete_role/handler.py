from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_role
from qa_authoring.application.role_errors import RoleInUseError

if TYPE_CHECKING:
    from qa_authoring.application.delete_role.command import DeleteRoleCommand
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository


class DeleteRoleHandler:
    """Guarded delete: refused while any user holds the role."""

    def __init__(self, roles: RoleRepository, users: UserRepository) -> None:
        self._roles = roles
        self._users = users

    async def __call__(self, command: DeleteRoleCommand) -> None:
        await load_role(self._roles, command.role_id)
        if await self._users.uses_role(command.role_id):
            raise RoleInUseError(command.role_id)
        await self._roles.delete(command.role_id)
