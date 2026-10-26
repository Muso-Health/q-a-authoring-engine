from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_response import AccessReferences, UserResult
from qa_authoring.application.role_errors import RoleNotFoundError
from qa_authoring.application.user_errors import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository
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


class UserViews:
    """User results with the roles, projects and languages of their assignments resolved."""

    def __init__(
        self, roles: RoleRepository, projects: ProjectRepository, languages: LanguageRepository
    ) -> None:
        self._roles = roles
        self._projects = projects
        self._languages = languages

    async def one(self, user: User) -> UserResult:
        return (await self.many((user,)))[0]

    async def many(self, users: Sequence[User]) -> tuple[UserResult, ...]:
        assignments = [a for user in users for a in user.assignments]
        project_ids = {a.project_id for a in assignments if a.project_id is not None}
        language_ids = {a.language_id for a in assignments if a.language_id is not None}
        projects = {i: p for i in project_ids if (p := await self._projects.get(i)) is not None}
        languages = {
            i: lang for i in language_ids if (lang := await self._languages.get(i)) is not None
        }
        references = AccessReferences(
            await self._roles.get_many({a.role_id for a in assignments}), projects, languages
        )
        return tuple(UserResult.of(user, references) for user in users)
