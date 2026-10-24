from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class AudioNotFoundError(Exception):
    def __init__(self, audio_id: UUID) -> None:
        super().__init__(f"audio {audio_id} not found")
        self.audio_id = audio_id


class UnsupportedAudioTypeError(Exception):
    """Raised when the upload is not a readable recording of an allowed type."""

    def __init__(self, mime_type: str | None) -> None:
        detail = "is not a readable audio recording" if mime_type is None else f"is {mime_type}"
        super().__init__(f"the uploaded file {detail}, which is not an accepted audio type")
        self.mime_type = mime_type


class AudioTooLargeError(Exception):
    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(f"the upload is {size_bytes} bytes; the maximum is {max_bytes}")
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
