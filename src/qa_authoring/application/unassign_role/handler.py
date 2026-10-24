from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_user, user_result
from qa_authoring.application.user_errors import RoleNotAssignedError

if TYPE_CHECKING:
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.unassign_role.command import UnassignRoleCommand


class UnassignRoleHandler:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def __call__(self, command: UnassignRoleCommand) -> UserResult:
        user = await load_user(self._users, command.user_id)
        if not user.unassign_role(command.role_id):
            raise RoleNotAssignedError(command.user_id, command.role_id)
        await self._users.update(user)
        return await user_result(self._roles, user)
