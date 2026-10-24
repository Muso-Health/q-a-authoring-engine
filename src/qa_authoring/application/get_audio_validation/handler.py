from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.audio_errors import AudioNotFoundError
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.get_audio_validation.command import GetAudioValidationQuery
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.application.validation_support import DecisionRecorder


class GetAudioValidationHandler:
    def __init__(self, qasets: QASetRepository, recorder: DecisionRecorder) -> None:
        self._qasets = qasets
        self._recorder = recorder

    async def __call__(self, query: GetAudioValidationQuery) -> ValidationResult:
        if await self._qasets.find_audio(query.audio_id) is None:
            raise AudioNotFoundError(query.audio_id)
        return await self._recorder.history(ValidationSubject.for_audio(query.audio_id))
