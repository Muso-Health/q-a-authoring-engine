from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import TranslationLinkResult

if TYPE_CHECKING:
    from qa_authoring.application.link_variants.command import LinkVariantsCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class LinkVariantsHandler:
    """Link two variants of the QA set as translations of each other (symmetric)."""

    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: LinkVariantsCommand) -> TranslationLinkResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        link = qaset.link_variants(command.variant_a_id, command.variant_b_id)
        await self._qasets.save(qaset)
        return TranslationLinkResult.of(link)
