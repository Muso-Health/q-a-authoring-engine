from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.user import User


class UserRepository(Protocol):
    async def add(self, user: User) -> None:
        """Raises ``EmailAlreadyExistsError`` if the email is taken."""
        ...

    async def get(self, user_id: UUID) -> User | None: ...

    async def find_by_email(self, email: str) -> User | None:
        """Case-insensitive."""
        ...

    async def list(self) -> tuple[User, ...]:
        """Ordered by email."""
        ...

    async def update(self, user: User) -> None:
        """Persist every attribute, role assignments included."""
        ...

    async def uses_role(self, role_id: UUID) -> bool: ...
