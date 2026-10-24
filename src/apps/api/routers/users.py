from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.access import (
    AssignRoleRequest,
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
    UsersResponse,
)
from config.container import Container
from qa_authoring.application.assign_role.command import AssignRoleCommand
from qa_authoring.application.create_user.command import CreateUserCommand
from qa_authoring.application.get_user.command import GetUserQuery
from qa_authoring.application.list_users.command import ListUsersQuery
from qa_authoring.application.unassign_role.command import UnassignRoleCommand
from qa_authoring.application.update_user.command import UpdateUserCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[requires(Permission.MANAGE_ACCESS)]
)

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest, container: ContainerDep) -> UserResponse:
    """Provision a user (active, no roles yet). 409 if the email is taken."""
    command = CreateUserCommand(email=body.email, display_name=body.display_name)
    return UserResponse.of(await container.run(container.build_create_user, command))


@router.get("")
async def list_users(container: ContainerDep) -> UsersResponse:
    return UsersResponse.of(await container.run(container.build_list_users, ListUsersQuery()))


@router.get("/{user_id}")
async def get_user(user_id: UUID, container: ContainerDep) -> UserResponse:
    return UserResponse.of(await container.run(container.build_get_user, GetUserQuery(user_id)))


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID, body: UpdateUserRequest, container: ContainerDep
) -> UserResponse:
    """Rename and/or (de)activate. There is no deletion: deactivate instead."""
    command = UpdateUserCommand(user_id, display_name=body.display_name, is_active=body.is_active)
    return UserResponse.of(await container.run(container.build_update_user, command))


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: UUID, body: AssignRoleRequest, response: Response, container: ContainerDep
) -> UserResponse:
    """Idempotent: 201 when assigned, 200 when the user already held the role."""
    command = AssignRoleCommand(user_id, body.role_id)
    result, created = await container.run(container.build_assign_role, command)
    if not created:
        response.status_code = status.HTTP_200_OK
    return UserResponse.of(result)


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_role(user_id: UUID, role_id: UUID, container: ContainerDep) -> Response:
    await container.run(container.build_unassign_role, UnassignRoleCommand(user_id, role_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
