from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import CurrentUser, requires, visible
from apps.api.dependencies import get_container
from apps.api.schemas.catalog import (
    CreateProjectRequest,
    ProjectResponse,
    ProjectsResponse,
    UpdateNamedRequest,
)
from config.container import Container
from qa_authoring.application.create_project.command import CreateProjectCommand
from qa_authoring.application.delete_project.command import DeleteProjectCommand
from qa_authoring.application.get_project.command import GetProjectQuery
from qa_authoring.application.list_projects.command import ListProjectsQuery
from qa_authoring.application.ports.resource_scopes import ResourceKind
from qa_authoring.application.update_project.command import UpdateProjectCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(prefix="/projects", tags=["projects"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "", status_code=status.HTTP_201_CREATED, dependencies=[requires(Permission.MANAGE_CATALOG)]
)
async def create_project(body: CreateProjectRequest, container: ContainerDep) -> ProjectResponse:
    """Create a project. 422 if the base language does not exist; it cannot change afterwards."""
    command = CreateProjectCommand(
        name=body.name, description=body.description, base_language_id=body.base_language_id
    )
    return ProjectResponse.of(await container.run(container.build_create_project, command))


@router.get("")
async def list_projects(user: CurrentUser, container: ContainerDep) -> ProjectsResponse:
    """The projects the caller can see: those any of their role assignments covers."""
    query = ListProjectsQuery(user.authorization.visible_project_ids)
    return ProjectsResponse.of(await container.run(container.build_list_projects, query))


@router.get("/{project_id}", dependencies=[visible(ResourceKind.PROJECT)])
async def get_project(project_id: UUID, container: ContainerDep) -> ProjectResponse:
    query = GetProjectQuery(project_id)
    return ProjectResponse.of(await container.run(container.build_get_project, query))


@router.patch("/{project_id}", dependencies=[requires(Permission.MANAGE_CATALOG)])
async def update_project(
    project_id: UUID, body: UpdateNamedRequest, container: ContainerDep
) -> ProjectResponse:
    """Edit the name and/or description. The base language is immutable."""
    command = UpdateProjectCommand(
        project_id, name=body.name, description=body.description_change()
    )
    return ProjectResponse.of(await container.run(container.build_update_project, command))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def delete_project(project_id: UUID, container: ContainerDep) -> Response:
    """409 while the project still has protocols."""
    await container.run(container.build_delete_project, DeleteProjectCommand(project_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
