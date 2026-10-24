from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.application.qaset_response import QASetResult
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.qaset import QASet

if TYPE_CHECKING:
    from qa_authoring.application.create_qaset.command import CreateQASetCommand
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class CreateQASetHandler:
    """Create a QA set in a theme with its first answer; no question variants yet."""

    def __init__(
        self, qasets: QASetRepository, themes: ThemeRepository, languages: LanguageRepository
    ) -> None:
        self._qasets = qasets
        self._themes = themes
        self._languages = languages

    async def __call__(self, command: CreateQASetCommand) -> QASetResult:
        if await self._themes.get(command.theme_id) is None:
            raise ThemeNotFoundError(command.theme_id)
        if await self._languages.get(command.language_id) is None:
            raise UnknownLanguageError(command.language_id)
        qaset = QASet.create(
            theme_id=command.theme_id,
            language_id=command.language_id,
            answer_text=command.answer_text,
        )
        await self._qasets.add(qaset)
        return QASetResult.of(qaset, {}, {})
