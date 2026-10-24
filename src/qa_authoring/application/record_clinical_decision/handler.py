from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.validation_errors import NoBaseLanguagePresenceError
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.record_clinical_decision.command import (
        RecordClinicalDecisionCommand,
    )
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.application.validation_support import (
        BaseLanguageResolver,
        DecisionRecorder,
    )


class RecordClinicalDecisionHandler:
    """Clinically validate or reject a QA set. Only a set answered in its project's base
    language can be reviewed clinically."""

    def __init__(
        self,
        qasets: QASetRepository,
        base_language: BaseLanguageResolver,
        recorder: DecisionRecorder,
    ) -> None:
        self._qasets = qasets
        self._base_language = base_language
        self._recorder = recorder

    async def __call__(
        self, command: RecordClinicalDecisionCommand
    ) -> tuple[ValidationResult, bool]:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        base = await self._base_language.of(qaset)
        if base not in {p.language_id for p in qaset.presences()}:
            raise NoBaseLanguagePresenceError(qaset.id)
        return await self._recorder.record(
            ValidationSubject.for_qaset(qaset.id),
            command.decision,
            actor_user_id=command.actor_user_id,
            note=command.note,
        )
