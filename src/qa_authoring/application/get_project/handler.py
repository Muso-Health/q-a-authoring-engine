from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProjectResult
from qa_authoring.application.project_errors import ProjectNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.get_project.command import GetProjectQuery
    from qa_authoring.application.ports.project_repository import ProjectRepository


class GetProjectHandler:
    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    async def __call__(self, query: GetProjectQuery) -> ProjectResult:
        project = await self._projects.get(query.project_id)
        if project is None:
            raise ProjectNotFoundError(query.project_id)
        return ProjectResult.of(project)
