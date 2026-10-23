from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.project_errors import ProjectHasProtocolsError, ProjectNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_project.command import DeleteProjectCommand
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository


class DeleteProjectHandler:
    """Guarded delete: refused while protocols still belong to the project."""

    def __init__(self, projects: ProjectRepository, protocols: ProtocolRepository) -> None:
        self._projects = projects
        self._protocols = protocols

    async def __call__(self, command: DeleteProjectCommand) -> None:
        if await self._projects.get(command.project_id) is None:
            raise ProjectNotFoundError(command.project_id)
        if await self._protocols.exists_for_project(command.project_id):
            raise ProjectHasProtocolsError(command.project_id)
        await self._projects.delete(command.project_id)
