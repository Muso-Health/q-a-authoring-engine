from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import intent_texts, load_qaset
from qa_authoring.application.qaset_response import QuestionVariantResult

if TYPE_CHECKING:
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.update_question_variant.command import (
        UpdateQuestionVariantCommand,
    )


class UpdateQuestionVariantHandler:
    def __init__(self, qasets: QASetRepository, intents: IntentRepository) -> None:
        self._qasets = qasets
        self._intents = intents

    async def __call__(self, command: UpdateQuestionVariantCommand) -> QuestionVariantResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        variant = qaset.update_variant(command.variant_id, command.text)
        await self._qasets.save(qaset)
        return QuestionVariantResult.of(qaset, variant, await intent_texts(self._intents, qaset))
