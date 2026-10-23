from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.language_errors import LanguageCodeAlreadyExistsError
from qa_authoring.application.language_response import LanguageResult
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.value_objects.language_code import LanguageCode

if TYPE_CHECKING:
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.register_language.command import RegisterLanguageCommand


class RegisterLanguageHandler:
    """Register a new language. The code must be well-formed and not already taken (the DB unique
    constraint backs this check against a concurrent registration)."""

    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def __call__(self, command: RegisterLanguageCommand) -> LanguageResult:
        code = LanguageCode(command.code)
        if await self._languages.find_by_code(code) is not None:
            raise LanguageCodeAlreadyExistsError(code.value)
        language = Language.register(code, command.name)
        await self._languages.add(language)
        return LanguageResult.of(language)
