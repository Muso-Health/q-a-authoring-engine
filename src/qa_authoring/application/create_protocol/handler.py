from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.catalog_response import ProtocolResult
from qa_authoring.application.project_errors import ProjectNotFoundError
from qa_authoring.domain.model.protocol import Protocol

if TYPE_CHECKING:
    from qa_authoring.application.create_protocol.command import CreateProtocolCommand
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository


class CreateProtocolHandler:
    def __init__(self, protocols: ProtocolRepository, projects: ProjectRepository) -> None:
        self._protocols = protocols
        self._projects = projects

    async def __call__(self, command: CreateProtocolCommand) -> ProtocolResult:
        if await self._projects.get(command.project_id) is None:
            raise ProjectNotFoundError(command.project_id)
        protocol = Protocol.create(
            project_id=command.project_id, name=command.name, description=command.description
        )
        await self._protocols.add(protocol)
        return ProtocolResult.of(protocol)
