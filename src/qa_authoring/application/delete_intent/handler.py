from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.intent_errors import IntentInUseError, IntentNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_intent.command import DeleteIntentCommand
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DeleteIntentHandler:
    """Guarded delete: refused while any question variant has the intent attached."""

    def __init__(self, intents: IntentRepository, qasets: QASetRepository) -> None:
        self._intents = intents
        self._qasets = qasets

    async def __call__(self, command: DeleteIntentCommand) -> None:
        if await self._intents.get(command.intent_id) is None:
            raise IntentNotFoundError(command.intent_id)
        if await self._qasets.uses_intent(command.intent_id):
            raise IntentInUseError(command.intent_id)
        await self._intents.delete(command.intent_id)
