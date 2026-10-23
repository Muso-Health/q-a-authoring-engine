from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class LinkAnswersCommand:
    qaset_id: UUID
    answer_a_id: UUID
    answer_b_id: UUID
