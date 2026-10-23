from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import intent_texts, load_qaset
from qa_authoring.application.qaset_response import LanguagePresenceResult

if TYPE_CHECKING:
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.update_answer.command import UpdateAnswerCommand


class UpdateAnswerHandler:
    def __init__(self, qasets: QASetRepository, intents: IntentRepository) -> None:
        self._qasets = qasets
        self._intents = intents

    async def __call__(self, command: UpdateAnswerCommand) -> LanguagePresenceResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.update_answer(command.language_id, command.text)
        await self._qasets.save(qaset)
        texts = await intent_texts(self._intents, qaset)
        return LanguagePresenceResult.of(qaset, qaset.presence(command.language_id), texts)
