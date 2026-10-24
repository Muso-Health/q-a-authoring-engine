from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.get_clinical_validation.command import (
        GetClinicalValidationQuery,
    )
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.application.validation_support import DecisionRecorder


class GetClinicalValidationHandler:
    def __init__(self, qasets: QASetRepository, recorder: DecisionRecorder) -> None:
        self._qasets = qasets
        self._recorder = recorder

    async def __call__(self, query: GetClinicalValidationQuery) -> ValidationResult:
        qaset = await load_qaset(self._qasets, query.qaset_id)
        return await self._recorder.history(ValidationSubject.for_qaset(qaset.id))
