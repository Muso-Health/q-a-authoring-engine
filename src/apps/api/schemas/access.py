from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.access_response import (
        AssignmentResult,
        CurrentUserResult,
        GrantResult,
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
    """A null (or absent) project or language means any."""

    role_id: UUID
    project_id: UUID | None = None
    language_id: UUID | None = None


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


class ProjectRefResponse(BaseModel):
    id: UUID
    name: str


class LanguageRefResponse(BaseModel):
    id: UUID
    code: str
    name: str


class AssignmentResponse(BaseModel):
    """A role held within a scope; a null project or language means any."""

    id: UUID
    role: RoleSummaryResponse
    project: ProjectRefResponse | None
    language: LanguageRefResponse | None

    @classmethod
    def of(cls, result: AssignmentResult) -> AssignmentResponse:
        project, language = result.project, result.language
        return cls(
            id=result.id,
            role=RoleSummaryResponse(id=result.role.id, name=result.role.name),
            project=None
            if project is None
            else ProjectRefResponse(id=project.id, name=project.name),
            language=None
            if language is None
            else LanguageRefResponse(id=language.id, code=language.code, name=language.name),
        )


class GrantResponse(BaseModel):
    """An effective permission within its scope (null means any), normalized to the
    permission's scope class: global permissions carry no scope, project ones no language."""

    permission: str
    project_id: UUID | None
    language_id: UUID | None

    @classmethod
    def of(cls, result: GrantResult) -> GrantResponse:
        return cls(
            permission=result.permission,
            project_id=result.project_id,
            language_id=result.language_id,
        )


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_active: bool
    assignments: list[AssignmentResponse]
    grants: list[GrantResponse]

    @classmethod
    def of(cls, result: UserResult) -> UserResponse:
        return cls(
            id=result.id,
            email=result.email,
            display_name=result.display_name,
            is_active=result.is_active,
            assignments=[AssignmentResponse.of(a) for a in result.assignments],
            grants=[GrantResponse.of(g) for g in result.grants],
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
    """The current user, their scoped assignments and effective grants, and every permission
    they hold in some scope, for the front to gate its UI."""

    id: UUID
    email: str
    display_name: str
    permissions: list[str]
    assignments: list[AssignmentResponse]
    grants: list[GrantResponse]

    @classmethod
    def of(cls, current: CurrentUserResult, user: UserResult) -> MeResponse:
        return cls(
            id=current.id,
            email=current.email,
            display_name=current.display_name,
            permissions=list(current.permissions),
            assignments=[AssignmentResponse.of(a) for a in user.assignments],
            grants=[GrantResponse.of(g) for g in current.grants],
        )


class PermissionsResponse(BaseModel):
    items: list[str]
