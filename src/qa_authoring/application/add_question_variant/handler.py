from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import NO_LOOKUPS, QuestionVariantResult

if TYPE_CHECKING:
    from qa_authoring.application.add_question_variant.command import AddQuestionVariantCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.validation_reset import ValidationResetter


class AddQuestionVariantHandler:
    """Add a question variant in a language the QA set already has an answer for."""

    def __init__(self, qasets: QASetRepository, resetter: ValidationResetter) -> None:
        self._qasets = qasets
        self._resetter = resetter

    async def __call__(self, command: AddQuestionVariantCommand) -> QuestionVariantResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        variant = qaset.add_variant(command.language_id, command.text)
        await self._qasets.save(qaset)
        await self._resetter.content_changed(
            qaset, command.language_id, item=None, actor_user_id=command.actor_user_id
        )
        return QuestionVariantResult.of(qaset, variant, NO_LOOKUPS)
