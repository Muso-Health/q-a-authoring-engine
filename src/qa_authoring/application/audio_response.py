from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — a field type on frozen result dataclasses
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

if TYPE_CHECKING:
    from qa_authoring.domain.model.qaset import AudioReference


@dataclass(frozen=True, slots=True)
class AudioResult:
    id: UUID
    mime_type: str
    duration_ms: int
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    @classmethod
    def of(cls, audio: AudioReference) -> AudioResult:
        return cls(
            audio.id,
            audio.mime_type,
            audio.duration_ms,
            audio.size_bytes,
            audio.checksum_sha256,
            audio.created_at,
        )


@dataclass(frozen=True, slots=True)
class PlaybackUrlResult:
    url: str
    expires_at: datetime
