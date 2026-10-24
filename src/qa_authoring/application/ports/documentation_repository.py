from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.documentation import Documentation


class DocumentationRepository(Protocol):
    async def add(self, documentation: Documentation) -> None: ...

    async def get(self, documentation_id: UUID) -> Documentation | None: ...

    async def list_by_theme(self, theme_id: UUID) -> tuple[Documentation, ...]:
        """In upload order."""
        ...

    async def delete(self, documentation_id: UUID) -> None: ...

    async def storage_uri_in_use(self, storage_uri: str) -> bool: ...
