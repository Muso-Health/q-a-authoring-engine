from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.intent_errors import IntentNotFoundError
from qa_authoring.application.intent_response import IntentResult

if TYPE_CHECKING:
    from qa_authoring.application.get_intent.command import GetIntentQuery
    from qa_authoring.application.ports.intent_repository import IntentRepository


class GetIntentHandler:
    def __init__(self, intents: IntentRepository) -> None:
        self._intents = intents

    async def __call__(self, query: GetIntentQuery) -> IntentResult:
        intent = await self._intents.get(query.intent_id)
        if intent is None:
            raise IntentNotFoundError(query.intent_id)
        return IntentResult.of(intent)
