from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.audio_response import AudioResult
from qa_authoring.application.audio_upload import release_blob
from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.audio_upload import AfterCommit, AudioUploader
    from qa_authoring.application.ports.audio_storage import AudioStoragePort
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.set_variant_audio.command import SetVariantAudioCommand


class SetVariantAudioHandler:
    """Upload a recording for the variant, replacing any previous one. The bytes are stored first;
    the replaced blob is deleted only after the new reference has committed. The flag says
    whether the variant had no audio before."""

    def __init__(
        self,
        qasets: QASetRepository,
        uploader: AudioUploader,
        storage: AudioStoragePort,
        after_commit: AfterCommit,
    ) -> None:
        self._qasets = qasets
        self._uploader = uploader
        self._storage = storage
        self._after_commit = after_commit

    async def __call__(self, command: SetVariantAudioCommand) -> tuple[AudioResult, bool]:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        qaset.variant_by_id(command.variant_id)
        audio = await self._uploader.upload(command.content)
        previous = qaset.set_variant_audio(command.variant_id, audio)
        await self._qasets.save(qaset)
        await release_blob(
            previous, qasets=self._qasets, storage=self._storage, after_commit=self._after_commit
        )
        return AudioResult.of(audio), previous is None
