from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class UserNotFoundError(Exception):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"user {user_id} not found")
        self.user_id = user_id


class EmailAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__(f"a user with email {email!r} already exists")
        self.email = email


class NotProvisionedError(Exception):
    """Raised when an authenticated identity maps to no active user."""

    def __init__(self, email: str) -> None:
        super().__init__(f"{email!r} has no active account; ask an administrator for access")
        self.email = email


class RoleNotAssignedError(Exception):
    def __init__(self, user_id: UUID, role_id: UUID) -> None:
        super().__init__(f"user {user_id} does not hold role {role_id}")
        self.user_id = user_id
        self.role_id = role_id
