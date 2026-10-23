from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_errors import LanguageNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_language.command import DeleteLanguageCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository


class DeleteLanguageHandler:
    """Plain delete — nothing references a language yet, so there is no guard to apply."""

    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def __call__(self, command: DeleteLanguageCommand) -> None:
        if await self._languages.get(command.language_id) is None:
            raise LanguageNotFoundError(command.language_id)
        await self._languages.delete(command.language_id)
