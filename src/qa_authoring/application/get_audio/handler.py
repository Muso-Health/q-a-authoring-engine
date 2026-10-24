from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.audio_errors import AudioNotFoundError
from qa_authoring.application.audio_response import AudioResult

if TYPE_CHECKING:
    from qa_authoring.application.get_audio.command import GetAudioQuery
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class GetAudioHandler:
    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, query: GetAudioQuery) -> AudioResult:
        audio = await self._qasets.find_audio(query.audio_id)
        if audio is None:
            raise AudioNotFoundError(query.audio_id)
        return AudioResult.of(audio)
