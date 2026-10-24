from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_response import QuestionVariantResult
    from qa_authoring.application.qaset_views import QASetViews
    from qa_authoring.application.update_question_variant.command import (
        UpdateQuestionVariantCommand,
    )
    from qa_authoring.application.validation_reset import ValidationResetter


class UpdateQuestionVariantHandler:
    def __init__(
        self, qasets: QASetRepository, views: QASetViews, resetter: ValidationResetter
    ) -> None:
        self._qasets = qasets
        self._views = views
        self._resetter = resetter

    async def __call__(self, command: UpdateQuestionVariantCommand) -> QuestionVariantResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        before = qaset.variant_by_id(command.variant_id).text
        variant = qaset.update_variant(command.variant_id, command.text)
        await self._qasets.save(qaset)
        if variant.text != before:
            await self._resetter.content_changed(
                qaset,
                variant.language_id,
                item=ValidationSubject.for_variant(variant.id),
                actor_user_id=command.actor_user_id,
            )
        return await self._views.variant(qaset, command.variant_id)
