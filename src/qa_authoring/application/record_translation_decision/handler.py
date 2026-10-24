from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.translation_items import translation_item
from qa_authoring.application.validation_errors import NotATranslationError

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.record_translation_decision.command import (
        RecordTranslationDecisionCommand,
    )
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.application.validation_support import (
        BaseLanguageResolver,
        DecisionRecorder,
    )


class RecordTranslationDecisionHandler:
    """Validate or reject one translated answer or question variant. Items in the project's
    base language are the source, not translations."""

    def __init__(
        self,
        qasets: QASetRepository,
        base_language: BaseLanguageResolver,
        recorder: DecisionRecorder,
    ) -> None:
        self._qasets = qasets
        self._base_language = base_language
        self._recorder = recorder

    async def __call__(
        self, command: RecordTranslationDecisionCommand
    ) -> tuple[ValidationResult, bool]:
        item = await translation_item(
            self._qasets, answer_id=command.answer_id, variant_id=command.variant_id
        )
        if item.language_id == await self._base_language.of(item.qaset):
            raise NotATranslationError(item.item_id)
        return await self._recorder.record(
            item.subject, command.decision, actor_user_id=command.actor_user_id, note=command.note
        )
