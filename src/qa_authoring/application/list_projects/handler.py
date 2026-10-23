from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProjectResult

if TYPE_CHECKING:
    from qa_authoring.application.list_projects.command import ListProjectsQuery
    from qa_authoring.application.ports.project_repository import ProjectRepository


class ListProjectsHandler:
    """Every project, ordered by name."""

    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    async def __call__(self, query: ListProjectsQuery) -> tuple[ProjectResult, ...]:
        return tuple(ProjectResult.of(project) for project in await self._projects.list())
