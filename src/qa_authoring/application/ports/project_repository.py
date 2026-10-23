from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.project import Project


class ProjectRepository(Protocol):
    async def add(self, project: Project) -> None:
        """Raises ``UnknownBaseLanguageError`` if the base language does not exist."""
        ...

    async def get(self, project_id: UUID) -> Project | None: ...

    async def list(self) -> tuple[Project, ...]:
        """Every project, ordered by name."""
        ...

    async def update(self, project: Project) -> None: ...

    async def delete(self, project_id: UUID) -> None:
        """Raises ``ProjectHasProtocolsError`` if protocols still reference it."""
        ...

    async def uses_base_language(self, language_id: UUID) -> bool: ...
