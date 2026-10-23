from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProjectResult
from qa_authoring.application.project_errors import UnknownBaseLanguageError
from qa_authoring.domain.model.project import Project

if TYPE_CHECKING:
    from qa_authoring.application.create_project.command import CreateProjectCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository


class CreateProjectHandler:
    """Create a project over an existing base language (fixed for the project's lifetime)."""

    def __init__(self, projects: ProjectRepository, languages: LanguageRepository) -> None:
        self._projects = projects
        self._languages = languages

    async def __call__(self, command: CreateProjectCommand) -> ProjectResult:
        if await self._languages.get(command.base_language_id) is None:
            raise UnknownBaseLanguageError(command.base_language_id)
        project = Project.create(
            name=command.name,
            base_language_id=command.base_language_id,
            description=command.description,
        )
        await self._projects.add(project)
        return ProjectResult.of(project)
