from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from qa_authoring.application.audio_errors import AudioNotFoundError
from qa_authoring.application.audio_response import PlaybackUrlResult

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from qa_authoring.application.audio_policy import AudioPolicy
    from qa_authoring.application.get_audio_playback_url.command import GetAudioPlaybackUrlQuery
    from qa_authoring.application.ports.audio_storage import AudioStoragePort
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class GetAudioPlaybackUrlHandler:
    """A short-lived signed URL for playing the recording, minted on demand."""

    def __init__(
        self,
        qasets: QASetRepository,
        storage: AudioStoragePort,
        policy: AudioPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self._qasets = qasets
        self._storage = storage
        self._policy = policy
        self._clock = clock

    async def __call__(self, query: GetAudioPlaybackUrlQuery) -> PlaybackUrlResult:
        audio = await self._qasets.find_audio(query.audio_id)
        if audio is None:
            raise AudioNotFoundError(query.audio_id)
        ttl = self._policy.playback_url_ttl_seconds
        expires_at = self._clock() + timedelta(seconds=ttl)
        url = await self._storage.signed_url(audio.storage_uri, ttl)
        return PlaybackUrlResult(url=url, expires_at=expires_at)
