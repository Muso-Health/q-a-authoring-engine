from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_response import QuestionVariantResult
    from qa_authoring.application.qaset_views import QASetViews
    from qa_authoring.application.update_question_variant.command import (
        UpdateQuestionVariantCommand,
    )


class UpdateQuestionVariantHandler:
    def __init__(self, qasets: QASetRepository, views: QASetViews) -> None:
        self._qasets = qasets
        self._views = views

    async def __call__(self, command: UpdateQuestionVariantCommand) -> QuestionVariantResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.update_variant(command.variant_id, command.text)
        await self._qasets.save(qaset)
        return await self._views.variant(qaset, command.variant_id)
