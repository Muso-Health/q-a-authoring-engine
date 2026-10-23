from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProtocolResult
from qa_authoring.application.project_errors import ProjectNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.list_protocols.command import ListProtocolsQuery
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository


class ListProtocolsHandler:
    """The project's protocols, ordered by name; the project must exist."""

    def __init__(self, protocols: ProtocolRepository, projects: ProjectRepository) -> None:
        self._protocols = protocols
        self._projects = projects

    async def __call__(self, query: ListProtocolsQuery) -> tuple[ProtocolResult, ...]:
        if await self._projects.get(query.project_id) is None:
            raise ProjectNotFoundError(query.project_id)
        return tuple(
            ProtocolResult.of(row)
            for row in await self._protocols.list_by_project(query.project_id)
        )
