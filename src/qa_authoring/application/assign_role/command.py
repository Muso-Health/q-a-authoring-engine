from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class AssignRoleCommand:
    """A null project or language means any."""

    user_id: UUID
    role_id: UUID
    project_id: UUID | None = None
    language_id: UUID | None = None
