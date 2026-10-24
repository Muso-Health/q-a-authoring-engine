from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class ValidationQueueQuery:
    """The filter of a validation queue, as the caller sent it."""

    project_id: UUID | None = None
    theme_id: UUID | None = None
    state: str = "pending"
    limit: int = 50
    cursor: str | None = None
