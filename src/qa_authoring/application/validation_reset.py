from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.domain.model.validation import ValidationState, ValidationSubject

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from uuid import UUID

    from qa_authoring.application.ports.validation_repository import ValidationRepository
    from qa_authoring.application.validation_support import BaseLanguageResolver
    from qa_authoring.domain.model.qaset import QASet
    from qa_authoring.domain.model.validation import Validation


class ValidationResetter:
    """Returns decided validations to pending when the content they judged changes, so nothing
    differing from what was validated can pass as validated. A change in the project's base
    language resets the QA set's clinical validation; a change to a translated item's own text
    resets that item's translation validation. Call it after a content change, in its unit of
    work, with the editing user as actor."""

    def __init__(
        self,
        validations: ValidationRepository,
        base_language: BaseLanguageResolver,
        clock: Callable[[], datetime],
    ) -> None:
        self._validations = validations
        self._base_language = base_language
        self._clock = clock

    async def content_changed(
        self,
        qaset: QASet,
        language_id: UUID,
        *,
        item: ValidationSubject | None,
        actor_user_id: UUID,
    ) -> None:
        """``language_id`` is the language whose content changed; ``item`` the answer or
        variant whose own text changed, if any."""
        clinical = await self._decided(ValidationSubject.for_qaset(qaset.id))
        translation = None if item is None else await self._decided(item)
        if clinical is None and translation is None:
            return
        affected = clinical if language_id == await self._base_language.of(qaset) else translation
        if affected is not None:
            affected.reset(actor_user_id=actor_user_id, at=self._clock())
            await self._validations.save(affected)

    async def _decided(self, subject: ValidationSubject) -> Validation | None:
        validation = await self._validations.get_for(subject)
        if validation is None or validation.current_state is ValidationState.PENDING:
            return None
        return validation
