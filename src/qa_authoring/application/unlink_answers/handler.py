from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.unlink_answers.command import UnlinkAnswersCommand


class UnlinkAnswersHandler:
    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, command: UnlinkAnswersCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.unlink_answers(command.link_id)
        await self._qasets.save(qaset)
