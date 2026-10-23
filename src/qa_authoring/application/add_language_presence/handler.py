from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import LanguagePresenceResult

if TYPE_CHECKING:
    from qa_authoring.application.add_language_presence.command import (
        AddLanguagePresenceCommand,
    )
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class AddLanguagePresenceHandler:
    """Add a language to a QA set by giving its answer in that language."""

    def __init__(self, qasets: QASetRepository, languages: LanguageRepository) -> None:
        self._qasets = qasets
        self._languages = languages

    async def __call__(self, command: AddLanguagePresenceCommand) -> LanguagePresenceResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        if await self._languages.get(command.language_id) is None:
            raise UnknownLanguageError(command.language_id)
        qaset.add_language(command.language_id, command.answer_text)
        await self._qasets.save(qaset)
        return LanguagePresenceResult.of(qaset, qaset.presence(command.language_id), {})
