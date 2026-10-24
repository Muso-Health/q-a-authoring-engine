from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import uuid4

from qa_authoring.application.audio_errors import AudioTooLargeError, UnsupportedAudioTypeError
from qa_authoring.application.ports.audio_probe import UnreadableAudioError
from qa_authoring.domain.model.qaset import AudioReference

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from qa_authoring.application.audio_policy import AudioPolicy
    from qa_authoring.application.ports.audio_probe import AudioProbePort
    from qa_authoring.application.ports.audio_storage import AudioStoragePort
    from qa_authoring.application.ports.qaset_repository import QASetRepository

type AfterCommit = Callable[[Callable[[], Awaitable[None]]], None]


class AudioUploader:
    """Validates an upload against the policy, derives its metadata from the bytes (size and
    checksum here, duration and type from the probe) and stores it. Storage happens before any
    reference is persisted, so a committed reference never points at a missing blob."""

    def __init__(
        self,
        storage: AudioStoragePort,
        probe: AudioProbePort,
        policy: AudioPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self._storage = storage
        self._probe = probe
        self._policy = policy
        self._clock = clock

    async def upload(self, content: bytes) -> AudioReference:
        if len(content) > self._policy.max_upload_bytes:
            raise AudioTooLargeError(len(content), self._policy.max_upload_bytes)
        if not content:
            raise UnsupportedAudioTypeError(None)
        try:
            probed = await self._probe.probe(content)
        except UnreadableAudioError as exc:
            raise UnsupportedAudioTypeError(None) from exc
        if probed.mime_type not in self._policy.allowed_mime_types:
            raise UnsupportedAudioTypeError(probed.mime_type)
        storage_uri = await self._storage.store(content, probed.mime_type)
        return AudioReference(
            id=uuid4(),
            storage_uri=storage_uri,
            mime_type=probed.mime_type,
            duration_ms=probed.duration_ms,
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            created_at=self._clock(),
        )


async def release_blob(
    released: AudioReference | None,
    *,
    qasets: QASetRepository,
    storage: AudioStoragePort,
    after_commit: AfterCommit,
) -> None:
    """Schedule the deletion of a no-longer-referenced blob for after the commit. Call it after
    saving the aggregate. Content-addressed blobs can be shared, so one still referenced stays."""
    if released is None or await qasets.storage_uri_in_use(released.storage_uri):
        return
    storage_uri = released.storage_uri

    async def delete() -> None:
        await storage.delete(storage_uri)

    after_commit(delete)
