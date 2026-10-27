from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_errors import AnswerAlreadyExistsError
from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.theme_answers import qasets_by_answer
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.qaset_response import LanguagePresenceResult
    from qa_authoring.application.qaset_views import QASetViews
    from qa_authoring.application.update_answer.command import UpdateAnswerCommand
    from qa_authoring.application.validation_reset import ValidationResetter
    from qa_authoring.application.validation_support import BaseLanguageResolver
    from qa_authoring.domain.model.qaset import QASet


class UpdateAnswerHandler:
    """Edit a language's answer. A theme holds each base-language answer once: renaming one onto
    another QA set's answer is refused (the theme is locked for the check)."""

    def __init__(
        self,
        qasets: QASetRepository,
        themes: ThemeRepository,
        base_language: BaseLanguageResolver,
        views: QASetViews,
        resetter: ValidationResetter,
    ) -> None:
        self._qasets = qasets
        self._themes = themes
        self._base_language = base_language
        self._views = views
        self._resetter = resetter

    async def __call__(self, command: UpdateAnswerCommand) -> LanguagePresenceResult:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        before = qaset.presence(command.language_id).answer.text
        answer = qaset.update_answer(command.language_id, command.text)
        if answer.text != before and command.language_id == await self._base_language.of(qaset):
            await self._refuse_a_taken_answer(qaset, answer.text, command.language_id)
        await self._qasets.save(qaset)
        if answer.text != before:
            await self._resetter.content_changed(
                qaset,
                command.language_id,
                item=ValidationSubject.for_answer(answer.id),
                actor_user_id=command.actor_user_id,
            )
        return await self._views.presence(qaset, command.language_id)

    async def _refuse_a_taken_answer(self, qaset: QASet, text: str, language_id: UUID) -> None:
        await self._themes.get_for_update(qaset.theme_id)
        others = await qasets_by_answer(self._qasets, qaset.theme_id, language_id)
        existing = others.get(text)
        if existing is not None and existing.id != qaset.id:
            raise AnswerAlreadyExistsError(existing.id)
