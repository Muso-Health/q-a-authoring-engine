from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.intent_errors import IntentNotFoundError
from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.attach_intent.command import AttachIntentCommand
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_response import QuestionVariantResult
    from qa_authoring.application.qaset_views import QASetViews


class AttachIntentHandler:
    """Tag a question variant with a catalogue intent. Idempotent: the flag says whether the
    attachment was created. Never propagates across translation links."""

    def __init__(
        self, qasets: QASetRepository, intents: IntentRepository, views: QASetViews
    ) -> None:
        self._qasets = qasets
        self._intents = intents
        self._views = views

    async def __call__(self, command: AttachIntentCommand) -> tuple[QuestionVariantResult, bool]:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        if await self._intents.get(command.intent_id) is None:
            raise IntentNotFoundError(command.intent_id)
        created = qaset.attach_intent(command.variant_id, command.intent_id)
        if created:
            await self._qasets.save(qaset)
        return await self._views.variant(qaset, command.variant_id), created
