from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.audio_errors import AudioNotFoundError
from qa_authoring.domain.model.validation import ValidationSubject

if TYPE_CHECKING:
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.record_audio_decision.command import RecordAudioDecisionCommand
    from qa_authoring.application.validation_response import ValidationResult
    from qa_authoring.application.validation_support import DecisionRecorder


class RecordAudioDecisionHandler:
    """Validate or reject the quality of one recording."""

    def __init__(self, qasets: QASetRepository, recorder: DecisionRecorder) -> None:
        self._qasets = qasets
        self._recorder = recorder

    async def __call__(self, command: RecordAudioDecisionCommand) -> tuple[ValidationResult, bool]:
        if await self._qasets.find_audio(command.audio_id) is None:
            raise AudioNotFoundError(command.audio_id)
        return await self._recorder.record(
            ValidationSubject.for_audio(command.audio_id),
            command.decision,
            actor_user_id=command.actor_user_id,
            note=command.note,
        )
