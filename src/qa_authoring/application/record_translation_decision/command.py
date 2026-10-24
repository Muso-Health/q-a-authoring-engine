from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class RecordTranslationDecisionCommand:
    """The subject is exactly one of ``answer_id`` / ``variant_id``."""

    decision: str
    actor_user_id: UUID
    answer_id: UUID | None = None
    variant_id: UUID | None = None
    note: str | None = None
