from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class RoleNotFoundError(Exception):
    def __init__(self, role_id: UUID) -> None:
        super().__init__(f"role {role_id} not found")
        self.role_id = role_id


class RoleNameExistsError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"a role named {name!r} already exists")
        self.name = name


class RoleInUseError(Exception):
    def __init__(self, role_id: UUID) -> None:
        super().__init__(f"role {role_id} is assigned to users")
        self.role_id = role_id
