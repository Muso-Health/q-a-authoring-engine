from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_user

if TYPE_CHECKING:
    from qa_authoring.application.access_loading import UserViews
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.application.update_user.command import UpdateUserCommand


class UpdateUserHandler:
    def __init__(self, users: UserRepository, views: UserViews) -> None:
        self._users = users
        self._views = views

    async def __call__(self, command: UpdateUserCommand) -> UserResult:
        user = await load_user(self._users, command.user_id)
        if command.display_name is not None:
            user.rename(command.display_name)
        if command.is_active is not None:
            user.set_active(command.is_active)
        await self._users.update(user)
        return await self._views.one(user)
