from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.theme import Theme


class ThemeRepository(Protocol):
    async def add(self, theme: Theme) -> None:
        """Raises ``ProtocolNotFoundError`` if the protocol does not exist."""
        ...

    async def get(self, theme_id: UUID) -> Theme | None: ...

    async def list_by_protocol(self, protocol_id: UUID) -> tuple[Theme, ...]:
        """The protocol's themes, ordered by name."""
        ...

    async def update(self, theme: Theme) -> None: ...

    async def delete(self, theme_id: UUID) -> None: ...

    async def exists_for_protocol(self, protocol_id: UUID) -> bool: ...
