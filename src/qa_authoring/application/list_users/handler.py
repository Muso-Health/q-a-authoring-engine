from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import UserResult

if TYPE_CHECKING:
    from qa_authoring.application.list_users.command import ListUsersQuery
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository


class ListUsersHandler:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def __call__(self, query: ListUsersQuery) -> tuple[UserResult, ...]:
        users = await self._users.list()
        roles = await self._roles.get_many({r for user in users for r in user.role_ids})
        return tuple(UserResult.of(user, roles) for user in users)
