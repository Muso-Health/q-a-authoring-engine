from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.access_loading import load_role, load_user
from qa_authoring.application.language_errors import LanguageNotFoundError
from qa_authoring.application.project_errors import ProjectNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.access_loading import UserViews
    from qa_authoring.application.access_response import UserResult
    from qa_authoring.application.assign_role.command import AssignRoleCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository


class AssignRoleHandler:
    """Idempotent per (role, project, language): the flag says whether it was newly assigned."""

    def __init__(
        self,
        users: UserRepository,
        roles: RoleRepository,
        projects: ProjectRepository,
        languages: LanguageRepository,
        views: UserViews,
    ) -> None:
        self._users = users
        self._roles = roles
        self._projects = projects
        self._languages = languages
        self._views = views

    async def __call__(self, command: AssignRoleCommand) -> tuple[UserResult, bool]:
        user = await load_user(self._users, command.user_id)
        await load_role(self._roles, command.role_id)
        if command.project_id is not None and await self._projects.get(command.project_id) is None:
            raise ProjectNotFoundError(command.project_id)
        if (
            command.language_id is not None
            and await self._languages.get(command.language_id) is None
        ):
            raise LanguageNotFoundError(command.language_id)
        _, created = user.assign(
            command.role_id, project_id=command.project_id, language_id=command.language_id
        )
        if created:
            await self._users.update(user)
        return await self._views.one(user), created
