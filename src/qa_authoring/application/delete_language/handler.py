from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_errors import LanguageInUseError, LanguageNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_language.command import DeleteLanguageCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DeleteLanguageHandler:
    """Guarded delete: refused while a project's base language or any QA set uses it."""

    def __init__(
        self,
        languages: LanguageRepository,
        projects: ProjectRepository,
        qasets: QASetRepository,
    ) -> None:
        self._languages = languages
        self._projects = projects
        self._qasets = qasets

    async def __call__(self, command: DeleteLanguageCommand) -> None:
        if await self._languages.get(command.language_id) is None:
            raise LanguageNotFoundError(command.language_id)
        if await self._projects.uses_base_language(
            command.language_id
        ) or await self._qasets.uses_language(command.language_id):
            raise LanguageInUseError(command.language_id)
        await self._languages.delete(command.language_id)
