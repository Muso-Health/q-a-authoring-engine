from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass

from qa_authoring.domain.model.authorization import Authorization


@dataclass(frozen=True, slots=True)
class ValidationQueueQuery:
    """The filter of a validation queue as the caller sent it, and what the caller may validate
    (nothing by default)."""

    project_id: UUID | None = None
    theme_id: UUID | None = None
    state: str = "pending"
    limit: int = 50
    cursor: str | None = None
    authorization: Authorization = field(default_factory=lambda: Authorization((), frozenset()))
