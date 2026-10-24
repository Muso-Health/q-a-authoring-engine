from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.catalog import (
    CreateNamedRequest,
    ProtocolResponse,
    ProtocolsResponse,
    UpdateNamedRequest,
)
from config.container import Container
from qa_authoring.application.create_protocol.command import CreateProtocolCommand
from qa_authoring.application.delete_protocol.command import DeleteProtocolCommand
from qa_authoring.application.get_protocol.command import GetProtocolQuery
from qa_authoring.application.list_protocols.command import ListProtocolsQuery
from qa_authoring.application.update_protocol.command import UpdateProtocolCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["protocols"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "/projects/{project_id}/protocols",
    status_code=status.HTTP_201_CREATED,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def create_protocol(
    project_id: UUID, body: CreateNamedRequest, container: ContainerDep
) -> ProtocolResponse:
    """Create a protocol under a project. 404 if the project does not exist."""
    command = CreateProtocolCommand(
        project_id=project_id, name=body.name, description=body.description
    )
    return ProtocolResponse.of(await container.run(container.build_create_protocol, command))


@router.get("/projects/{project_id}/protocols")
async def list_protocols(project_id: UUID, container: ContainerDep) -> ProtocolsResponse:
    query = ListProtocolsQuery(project_id)
    return ProtocolsResponse.of(await container.run(container.build_list_protocols, query))


@router.get("/protocols/{protocol_id}")
async def get_protocol(protocol_id: UUID, container: ContainerDep) -> ProtocolResponse:
    query = GetProtocolQuery(protocol_id)
    return ProtocolResponse.of(await container.run(container.build_get_protocol, query))


@router.patch("/protocols/{protocol_id}", dependencies=[requires(Permission.MANAGE_CATALOG)])
async def update_protocol(
    protocol_id: UUID, body: UpdateNamedRequest, container: ContainerDep
) -> ProtocolResponse:
    command = UpdateProtocolCommand(
        protocol_id, name=body.name, description=body.description_change()
    )
    return ProtocolResponse.of(await container.run(container.build_update_protocol, command))


@router.delete(
    "/protocols/{protocol_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def delete_protocol(protocol_id: UUID, container: ContainerDep) -> Response:
    """409 while the protocol still has themes."""
    await container.run(container.build_delete_protocol, DeleteProtocolCommand(protocol_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
