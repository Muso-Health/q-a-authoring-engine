from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.delete_question_variant.command import (
        DeleteQuestionVariantCommand,
    )
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.validation_reset import ValidationResetter


class DeleteQuestionVariantHandler:
    def __init__(self, qasets: QASetRepository, resetter: ValidationResetter) -> None:
        self._qasets = qasets
        self._resetter = resetter

    async def __call__(self, command: DeleteQuestionVariantCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        language_id = qaset.variant_by_id(command.variant_id).language_id
        qaset.remove_variant(command.variant_id)
        await self._qasets.save(qaset)
        await self._resetter.content_changed(
            qaset, language_id, item=None, actor_user_id=command.actor_user_id
        )
