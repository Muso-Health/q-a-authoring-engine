from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qa_authoring.application.access_loading import UserViews
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.list_users.command import ListUsersQuery
    from qa_authoring.application.ports.user_repository import UserRepository


class ListUsersHandler:
    def __init__(self, users: UserRepository, views: UserViews) -> None:
        self._users = users
        self._views = views

    async def __call__(self, query: ListUsersQuery) -> tuple[UserResult, ...]:
        return await self._views.many(await self._users.list())
