from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_errors import LanguageNotFoundError
from qa_authoring.application.language_response import LanguageResult

if TYPE_CHECKING:
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.update_language.command import UpdateLanguageCommand


class UpdateLanguageHandler:
    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def __call__(self, command: UpdateLanguageCommand) -> LanguageResult:
        language = await self._languages.get(command.language_id)
        if language is None:
            raise LanguageNotFoundError(command.language_id)
        language.rename(command.name)
        await self._languages.update(language)
        return LanguageResult.of(language)
