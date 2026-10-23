from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class CreateProjectCommand:
    name: str
    description: str | None
    base_language_id: UUID
