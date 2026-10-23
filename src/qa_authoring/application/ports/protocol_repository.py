from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.protocol import Protocol as ClinicalProtocol


class ProtocolRepository(Protocol):
    async def add(self, protocol: ClinicalProtocol) -> None:
        """Raises ``ProjectNotFoundError`` if the project does not exist."""
        ...

    async def get(self, protocol_id: UUID) -> ClinicalProtocol | None: ...

    async def list_by_project(self, project_id: UUID) -> tuple[ClinicalProtocol, ...]:
        """The project's protocols, ordered by name."""
        ...

    async def update(self, protocol: ClinicalProtocol) -> None: ...

    async def delete(self, protocol_id: UUID) -> None:
        """Raises ``ProtocolHasThemesError`` if themes still reference it."""
        ...

    async def exists_for_project(self, project_id: UUID) -> bool: ...
