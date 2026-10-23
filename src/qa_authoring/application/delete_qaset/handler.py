from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.delete_qaset.command import DeleteQASetCommand
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DeleteQASetHandler:
    """Delete the QA set with the answers and question variants it owns."""

    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: DeleteQASetCommand) -> None:
        await load_qaset(self._qasets, command.qaset_id)
        await self._qasets.delete(command.qaset_id)
