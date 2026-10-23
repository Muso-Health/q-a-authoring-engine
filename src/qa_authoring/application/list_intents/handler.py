from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.intent_response import IntentResult

if TYPE_CHECKING:
    from qa_authoring.application.list_intents.command import ListIntentsQuery
    from qa_authoring.application.ports.intent_repository import IntentRepository


class ListIntentsHandler:
    """The catalogue, optionally narrowed to intents whose normalized text starts with a prefix."""

    def __init__(self, intents: IntentRepository) -> None:
        self._intents = intents

    async def __call__(self, query: ListIntentsQuery) -> tuple[IntentResult, ...]:
        return tuple(IntentResult.of(i) for i in await self._intents.list(query.prefix))
