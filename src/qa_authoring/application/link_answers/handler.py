from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import TranslationLinkResult

if TYPE_CHECKING:
    from qa_authoring.application.link_answers.command import LinkAnswersCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class LinkAnswersHandler:
    """Link two answers of the QA set as translations of each other (symmetric)."""

    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: LinkAnswersCommand) -> TranslationLinkResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        link = qaset.link_answers(command.answer_a_id, command.answer_b_id)
        await self._qasets.save(qaset)
        return TranslationLinkResult.of(link)
