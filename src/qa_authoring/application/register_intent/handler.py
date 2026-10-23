from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.intent_response import IntentResult
from qa_authoring.domain.model.intent import Intent

if TYPE_CHECKING:
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.register_intent.command import RegisterIntentCommand


class RegisterIntentHandler:
    """Get-or-create by normalized text; the flag says whether the intent was created."""

    def __init__(self, intents: IntentRepository) -> None:
        self._intents = intents

    async def __call__(self, command: RegisterIntentCommand) -> tuple[IntentResult, bool]:
        intent, created = await self._intents.get_or_create(Intent.register(command.text))
        return IntentResult.of(intent), created
