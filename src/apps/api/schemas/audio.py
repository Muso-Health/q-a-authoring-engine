from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from apps.api.schemas.validation import ValidationStateResponse

if TYPE_CHECKING:
    from qa_authoring.application.audio_response import AudioResult, PlaybackUrlResult
    from qa_authoring.application.qaset_response import AudioSummaryResult


class AudioSummaryResponse(BaseModel):
    """An item's recording as listed in a QA set; play it via its playback-url."""

    audio_id: UUID
    mime_type: str
    duration_ms: int
    size_bytes: int
    checksum_sha256: str
    audio_validation: ValidationStateResponse | None

    @classmethod
    def of(cls, result: AudioSummaryResult | None) -> AudioSummaryResponse | None:
        if result is None:
            return None
        return cls(
            audio_id=result.audio_id,
            mime_type=result.mime_type,
            duration_ms=result.duration_ms,
            size_bytes=result.size_bytes,
            checksum_sha256=result.checksum_sha256,
            audio_validation=ValidationStateResponse.of(result.audio_validation),
        )


class AudioResponse(BaseModel):
    audio_id: UUID
    mime_type: str
    duration_ms: int
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    @classmethod
    def of(cls, result: AudioResult) -> AudioResponse:
        return cls(
            audio_id=result.id,
            mime_type=result.mime_type,
            duration_ms=result.duration_ms,
            size_bytes=result.size_bytes,
            checksum_sha256=result.checksum_sha256,
            created_at=result.created_at,
        )


class PlaybackUrlResponse(BaseModel):
    url: str
    expires_at: datetime

    @classmethod
    def of(cls, result: PlaybackUrlResult) -> PlaybackUrlResponse:
        return cls(url=result.url, expires_at=result.expires_at)
