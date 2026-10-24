from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_user, user_result

if TYPE_CHECKING:
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.get_user.command import GetUserQuery
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository


class GetUserHandler:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def __call__(self, query: GetUserQuery) -> UserResult:
        return await user_result(self._roles, await load_user(self._users, query.user_id))
