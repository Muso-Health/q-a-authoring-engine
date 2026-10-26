from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_user
from qa_authoring.application.user_errors import AssignmentNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.access_loading import UserViews
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.unassign_role.command import UnassignRoleCommand


class UnassignRoleHandler:
    def __init__(self, users: UserRepository, views: UserViews) -> None:
        self._users = users
        self._views = views

    async def __call__(self, command: UnassignRoleCommand) -> UserResult:
        user = await load_user(self._users, command.user_id)
        if not user.unassign(command.assignment_id):
            raise AssignmentNotFoundError(command.user_id, command.assignment_id)
        await self._users.update(user)
        return await self._views.one(user)
