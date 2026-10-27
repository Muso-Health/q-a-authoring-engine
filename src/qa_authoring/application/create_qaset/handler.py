from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_errors import AnswerAlreadyExistsError, UnknownLanguageError
from qa_authoring.application.qaset_response import NO_LOOKUPS, QASetResult
from qa_authoring.application.theme_answers import qasets_by_answer
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.qaset import QASet

if TYPE_CHECKING:
    from qa_authoring.application.create_qaset.command import CreateQASetCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.validation_support import BaseLanguageResolver


class CreateQASetHandler:
    """Create a QA set in a theme with its first answer; no question variants yet. A theme
    holds each base-language answer once: an answer it already has is refused, never merged
    (the theme is locked for the check)."""

    def __init__(
        self,
        qasets: QASetRepository,
        themes: ThemeRepository,
        languages: LanguageRepository,
        base_language: BaseLanguageResolver,
    ) -> None:
        self._qasets = qasets
        self._themes = themes
        self._languages = languages
        self._base_language = base_language

    async def __call__(self, command: CreateQASetCommand) -> QASetResult:
        if await self._themes.get_for_update(command.theme_id) is None:
            raise ThemeNotFoundError(command.theme_id)
        if await self._languages.get(command.language_id) is None:
            raise UnknownLanguageError(command.language_id)
        qaset = QASet.create(
            theme_id=command.theme_id,
            language_id=command.language_id,
            answer_text=command.answer_text,
        )
        base = await self._base_language.of_theme(command.theme_id)
        if command.language_id == base:
            answer = qaset.presence(base).answer.text
            existing = (await qasets_by_answer(self._qasets, command.theme_id, base)).get(answer)
            if existing is not None:
                raise AnswerAlreadyExistsError(existing.id)
        await self._qasets.add(qaset)
        return QASetResult.of(qaset, NO_LOOKUPS)
