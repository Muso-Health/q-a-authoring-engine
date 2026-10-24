from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class GenerateVariantsQuery:
    qaset_id: UUID
    answer_id: UUID
    context: str


@dataclass(frozen=True, slots=True)
class GeneratedVariantsResult:
    candidates: tuple[str, ...]
