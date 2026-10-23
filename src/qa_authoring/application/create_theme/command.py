from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class CreateThemeCommand:
    protocol_id: UUID
    name: str
    description: str | None
