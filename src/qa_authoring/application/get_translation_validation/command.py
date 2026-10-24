from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class GetTranslationValidationQuery:
    """The subject is exactly one of ``answer_id`` / ``variant_id``."""

    answer_id: UUID | None = None
    variant_id: UUID | None = None
