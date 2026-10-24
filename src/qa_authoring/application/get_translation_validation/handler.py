from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.translation_items import translation_item

if TYPE_CHECKING:
    from qa_authoring.application.get_translation_validation.command import (
        GetTranslationValidationQuery,
    )
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.application.validation_support import DecisionRecorder


class GetTranslationValidationHandler:
    def __init__(self, qasets: QASetRepository, recorder: DecisionRecorder) -> None:
        self._qasets = qasets
        self._recorder = recorder

    async def __call__(self, query: GetTranslationValidationQuery) -> ValidationResult:
        item = await translation_item(
            self._qasets, answer_id=query.answer_id, variant_id=query.variant_id
        )
        return await self._recorder.history(item.subject)
