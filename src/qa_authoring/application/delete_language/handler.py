from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_errors import LanguageInUseError, LanguageNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_language.command import DeleteLanguageCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository


class DeleteLanguageHandler:
    """Guarded delete: refused while a project uses the language as its base language."""

    def __init__(self, languages: LanguageRepository, projects: ProjectRepository) -> None:
        self._languages = languages
        self._projects = projects

    async def __call__(self, command: DeleteLanguageCommand) -> None:
        if await self._languages.get(command.language_id) is None:
            raise LanguageNotFoundError(command.language_id)
        if await self._projects.uses_base_language(command.language_id):
            raise LanguageInUseError(command.language_id)
        await self._languages.delete(command.language_id)
