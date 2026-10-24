from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import UserResult
from qa_authoring.application.role_errors import RoleNotFoundError
from qa_authoring.application.user_errors import UserNotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository
    from qa_authoring.domain.model.role import Role
    from qa_authoring.domain.model.user import User


async def load_user(users: UserRepository, user_id: UUID) -> User:
    user = await users.get(user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user


async def load_role(roles: RoleRepository, role_id: UUID) -> Role:
    role = await roles.get(role_id)
    if role is None:
        raise RoleNotFoundError(role_id)
    return role


async def user_result(roles: RoleRepository, user: User) -> UserResult:
    return UserResult.of(user, await roles.get_many(set(user.role_ids)))
