from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_role, load_user, user_result

if TYPE_CHECKING:
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.assign_role.command import AssignRoleCommand
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository


class AssignRoleHandler:
    """Idempotent: the flag says whether the role was newly assigned."""

    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def __call__(self, command: AssignRoleCommand) -> tuple[UserResult, bool]:
        user = await load_user(self._users, command.user_id)
        await load_role(self._roles, command.role_id)
        created = user.assign_role(command.role_id)
        if created:
            await self._users.update(user)
        return await user_result(self._roles, user), created
