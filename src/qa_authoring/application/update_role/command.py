from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class UpdateRoleCommand:
    """``None`` keeps the field; ``permission_codes`` replaces the whole set."""

    role_id: UUID
    name: str | None = None
    permission_codes: tuple[str, ...] | None = None
