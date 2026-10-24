from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_response import LanguagePresenceResult
    from qa_authoring.application.qaset_views import QASetViews
    from qa_authoring.application.update_answer.command import UpdateAnswerCommand
    from qa_authoring.application.validation_reset import ValidationResetter


class UpdateAnswerHandler:
    def __init__(
        self, qasets: QASetRepository, views: QASetViews, resetter: ValidationResetter
    ) -> None:
        self._qasets = qasets
        self._views = views
        self._resetter = resetter

    async def __call__(self, command: UpdateAnswerCommand) -> LanguagePresenceResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        before = qaset.presence(command.language_id).answer.text
        answer = qaset.update_answer(command.language_id, command.text)
        await self._qasets.save(qaset)
        if answer.text != before:
            await self._resetter.content_changed(
                qaset,
                command.language_id,
                item=ValidationSubject.for_answer(answer.id),
                actor_user_id=command.actor_user_id,
            )
        return await self._views.presence(qaset, command.language_id)
