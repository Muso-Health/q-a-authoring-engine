from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.access import (
    CreateRoleRequest,
    RoleResponse,
    RolesResponse,
    UpdateRoleRequest,
)
from config.container import Container
from qa_authoring.application.create_role.command import CreateRoleCommand
from qa_authoring.application.delete_role.command import DeleteRoleCommand
from qa_authoring.application.get_role.command import GetRoleQuery
from qa_authoring.application.list_roles.command import ListRolesQuery
from qa_authoring.application.update_role.command import UpdateRoleCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(
    prefix="/roles", tags=["roles"], dependencies=[requires(Permission.MANAGE_ACCESS)]
)

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_role(body: CreateRoleRequest, container: ContainerDep) -> RoleResponse:
    """422 ``unknown_permission`` for a code outside the catalogue (see ``GET /permissions``)."""
    command = CreateRoleCommand(name=body.name, permission_codes=tuple(body.permissions))
    return RoleResponse.of(await container.run(container.build_create_role, command))


@router.get("")
async def list_roles(container: ContainerDep) -> RolesResponse:
    return RolesResponse.of(await container.run(container.build_list_roles, ListRolesQuery()))


@router.get("/{role_id}")
async def get_role(role_id: UUID, container: ContainerDep) -> RoleResponse:
    return RoleResponse.of(await container.run(container.build_get_role, GetRoleQuery(role_id)))


@router.patch("/{role_id}")
async def update_role(
    role_id: UUID, body: UpdateRoleRequest, container: ContainerDep
) -> RoleResponse:
    codes = None if body.permissions is None else tuple(body.permissions)
    command = UpdateRoleCommand(role_id, name=body.name, permission_codes=codes)
    return RoleResponse.of(await container.run(container.build_update_role, command))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: UUID, container: ContainerDep) -> Response:
    """409 while any user holds the role."""
    await container.run(container.build_delete_role, DeleteRoleCommand(role_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
