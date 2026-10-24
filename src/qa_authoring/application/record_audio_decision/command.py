from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class RecordAudioDecisionCommand:
    audio_id: UUID
    decision: str
    actor_user_id: UUID
    note: str | None = None
