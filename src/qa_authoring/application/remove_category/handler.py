from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.remove_category.command import RemoveCategoryCommand


class RemoveCategoryHandler:
    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: RemoveCategoryCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.remove_category(command.category_id)
        await self._qasets.save(qaset)
