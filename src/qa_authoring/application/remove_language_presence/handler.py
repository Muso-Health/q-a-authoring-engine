from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.remove_language_presence.command import (
        RemoveLanguagePresenceCommand,
    )
    from qa_authoring.application.validation_reset import ValidationResetter


class RemoveLanguagePresenceHandler:
    """Remove a language's answer and every question variant in that language."""

    def __init__(self, qasets: QASetRepository, resetter: ValidationResetter) -> None:
        self._qasets = qasets
        self._resetter = resetter

    async def __call__(self, command: RemoveLanguagePresenceCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.remove_language(command.language_id)
        await self._qasets.save(qaset)
        await self._resetter.content_changed(
            qaset, command.language_id, item=None, actor_user_id=command.actor_user_id
        )
