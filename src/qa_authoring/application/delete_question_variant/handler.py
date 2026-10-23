from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.delete_question_variant.command import (
        DeleteQuestionVariantCommand,
    )
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DeleteQuestionVariantHandler:
    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: DeleteQuestionVariantCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.remove_variant(command.variant_id)
        await self._qasets.save(qaset)
