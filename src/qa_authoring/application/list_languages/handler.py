from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_response import LanguageResult

if TYPE_CHECKING:
    from qa_authoring.application.list_languages.command import ListLanguagesQuery
    from qa_authoring.application.ports.language_repository import LanguageRepository


class ListLanguagesHandler:
    """Every registered language, ordered by code."""

    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def __call__(self, query: ListLanguagesQuery) -> tuple[LanguageResult, ...]:
        return tuple(LanguageResult.of(language) for language in await self._languages.list())
