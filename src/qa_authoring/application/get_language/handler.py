from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_errors import LanguageNotFoundError
from qa_authoring.application.language_response import LanguageResult

if TYPE_CHECKING:
    from qa_authoring.application.get_language.command import GetLanguageQuery
    from qa_authoring.application.ports.language_repository import LanguageRepository


class GetLanguageHandler:
    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def __call__(self, query: GetLanguageQuery) -> LanguageResult:
        language = await self._languages.get(query.language_id)
        if language is None:
            raise LanguageNotFoundError(query.language_id)
        return LanguageResult.of(language)
