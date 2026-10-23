from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProjectResult
from qa_authoring.application.patch import apply_name_and_description
from qa_authoring.application.project_errors import ProjectNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.update_project.command import UpdateProjectCommand


class UpdateProjectHandler:
    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    async def __call__(self, command: UpdateProjectCommand) -> ProjectResult:
        project = await self._projects.get(command.project_id)
        if project is None:
            raise ProjectNotFoundError(command.project_id)
        apply_name_and_description(project, name=command.name, description=command.description)
        await self._projects.update(project)
        return ProjectResult.of(project)
