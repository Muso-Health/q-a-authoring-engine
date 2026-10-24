from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateRoleCommand:
    name: str
    permission_codes: tuple[str, ...]
