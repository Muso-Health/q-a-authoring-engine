from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.detach_intent.command import DetachIntentCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DetachIntentHandler:
    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: DetachIntentCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.detach_intent(command.variant_id, command.intent_id)
        await self._qasets.save(qaset)
