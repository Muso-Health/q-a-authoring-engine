from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass

from qa_authoring.application.patch import UNCHANGED, Unchanged


@dataclass(frozen=True, slots=True)
class UpdateGlossaryTermCommand:
    """``label=None`` keeps the label; ``note`` is cleared by None and kept by ``UNCHANGED``."""

    term_id: UUID
    label: str | None = None
    note: str | Unchanged | None = UNCHANGED
