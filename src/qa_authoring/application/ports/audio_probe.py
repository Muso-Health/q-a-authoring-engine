from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class UnreadableAudioError(Exception):
    """Raised when the bytes are not a readable audio recording."""


@dataclass(frozen=True, slots=True)
class ProbedAudio:
    duration_ms: int
    mime_type: str


class AudioProbePort(Protocol):
    async def probe(self, content: bytes) -> ProbedAudio:
        """Duration and container mime type, detected from the bytes themselves."""
        ...
