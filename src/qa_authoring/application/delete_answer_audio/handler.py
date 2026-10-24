from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.audio_upload import release_blob
from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.audio_upload import AfterCommit
    from qa_authoring.application.delete_answer_audio.command import DeleteAnswerAudioCommand
    from qa_authoring.application.ports.audio_storage import AudioStoragePort
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DeleteAnswerAudioHandler:
    """Remove the answer's recording: the reference is removed and committed, then the blob is
    deleted best-effort."""

    def __init__(
        self, qasets: QASetRepository, storage: AudioStoragePort, after_commit: AfterCommit
    ) -> None:
        self._qasets = qasets
        self._storage = storage
        self._after_commit = after_commit

    async def __call__(self, command: DeleteAnswerAudioCommand) -> None:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        removed = qaset.remove_answer_audio(command.answer_id)
        await self._qasets.save(qaset)
        await release_blob(
            removed, qasets=self._qasets, storage=self._storage, after_commit=self._after_commit
        )
