from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.access_response import (
        CurrentUserResult,
        RoleResult,
        UserResult,
    )


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateUserRequest(_Strict):
    email: str
    display_name: str


class UpdateUserRequest(_Strict):
    """An absent field is unchanged; ``is_active: false`` deactivates the user."""

    display_name: str | None = None
    is_active: bool | None = None


class AssignRoleRequest(_Strict):
    role_id: UUID


class CreateRoleRequest(_Strict):
    name: str
    permissions: list[str]


class UpdateRoleRequest(_Strict):
    """An absent field is unchanged; ``permissions`` replaces the whole set."""

    name: str | None = None
    permissions: list[str] | None = None


class RoleSummaryResponse(BaseModel):
    id: UUID
    name: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_active: bool
    roles: list[RoleSummaryResponse]

    @classmethod
    def of(cls, result: UserResult) -> UserResponse:
        return cls(
            id=result.id,
            email=result.email,
            display_name=result.display_name,
            is_active=result.is_active,
            roles=[RoleSummaryResponse(id=r.id, name=r.name) for r in result.roles],
        )


class UsersResponse(BaseModel):
    items: list[UserResponse]

    @classmethod
    def of(cls, results: Sequence[UserResult]) -> UsersResponse:
        return cls(items=[UserResponse.of(result) for result in results])


class RoleResponse(BaseModel):
    id: UUID
    name: str
    permissions: list[str]

    @classmethod
    def of(cls, result: RoleResult) -> RoleResponse:
        return cls(id=result.id, name=result.name, permissions=list(result.permissions))


class RolesResponse(BaseModel):
    items: list[RoleResponse]

    @classmethod
    def of(cls, results: Sequence[RoleResult]) -> RolesResponse:
        return cls(items=[RoleResponse.of(result) for result in results])


class MeResponse(BaseModel):
    """The current user and their effective permissions, for the front to gate its UI."""

    id: UUID
    email: str
    display_name: str
    permissions: list[str]

    @classmethod
    def of(cls, result: CurrentUserResult) -> MeResponse:
        return cls(
            id=result.id,
            email=result.email,
            display_name=result.display_name,
            permissions=list(result.permissions),
        )


class PermissionsResponse(BaseModel):
    items: list[str]
