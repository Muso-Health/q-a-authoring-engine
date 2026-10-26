from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_user

if TYPE_CHECKING:
    from qa_authoring.application.access_loading import UserViews
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.get_user.command import GetUserQuery
    from qa_authoring.application.ports.user_repository import UserRepository


class GetUserHandler:
    def __init__(self, users: UserRepository, views: UserViews) -> None:
        self._users = users
        self._views = views

    async def __call__(self, query: GetUserQuery) -> UserResult:
        return await self._views.one(await load_user(self._users, query.user_id))
