from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass

from qa_authoring.application.patch import UNCHANGED, Unchanged


@dataclass(frozen=True, slots=True)
class UpdateProjectCommand:
    """Partial update of the name and/or description; nothing else is editable."""

    project_id: UUID
    name: str | None = None
    description: str | Unchanged | None = UNCHANGED
