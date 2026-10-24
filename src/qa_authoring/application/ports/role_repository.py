from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.role import Role


class RoleRepository(Protocol):
    async def add(self, role: Role) -> None:
        """Raises ``RoleNameExistsError`` if the normalized name is taken."""
        ...

    async def get(self, role_id: UUID) -> Role | None: ...

    async def get_many(self, role_ids: set[UUID]) -> dict[UUID, Role]: ...

    async def find_by_key(self, key: str) -> Role | None: ...

    async def list(self) -> tuple[Role, ...]:
        """Ordered by normalized name."""
        ...

    async def update(self, role: Role) -> None:
        """Raises ``RoleNameExistsError`` if renamed onto a taken name."""
        ...

    async def delete(self, role_id: UUID) -> None:
        """Raises ``RoleInUseError`` if a user still holds it."""
        ...
