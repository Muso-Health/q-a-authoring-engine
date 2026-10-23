from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import QuestionVariantResult

if TYPE_CHECKING:
    from qa_authoring.application.add_question_variant.command import AddQuestionVariantCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class AddQuestionVariantHandler:
    """Add a question variant in a language the QA set already has an answer for."""

    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: AddQuestionVariantCommand) -> QuestionVariantResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        variant = qaset.add_variant(command.language_id, command.text)
        await self._qasets.save(qaset)
        return QuestionVariantResult.of(variant)
