from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    """``None`` keeps the field. Deactivation (``is_active=False``) replaces deletion."""

    user_id: UUID
    display_name: str | None = None
    is_active: bool | None = None
