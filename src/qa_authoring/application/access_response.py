from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

from qa_authoring.domain.model.authorization import Authorization

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from qa_authoring.domain.model.language import Language
    from qa_authoring.domain.model.permission import Permission
    from qa_authoring.domain.model.project import Project
    from qa_authoring.domain.model.role import Role
    from qa_authoring.domain.model.user import RoleAssignment, User


def _codes(permissions: Iterable[Permission]) -> tuple[str, ...]:
    return tuple(sorted(p.value for p in permissions))


@dataclass(frozen=True, slots=True)
class RoleResult:
    id: UUID
    name: str
    permissions: tuple[str, ...]

    @classmethod
    def of(cls, role: Role) -> RoleResult:
        return cls(role.id, role.name, _codes(role.permissions))


@dataclass(frozen=True, slots=True)
class RoleSummaryResult:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class ProjectRefResult:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class LanguageRefResult:
    id: UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    """A role held within a scope; a null project or language means any."""

    id: UUID
    role: RoleSummaryResult
    project: ProjectRefResult | None
    language: LanguageRefResult | None


@dataclass(frozen=True, slots=True)
class GrantResult:
    permission: str
    project_id: UUID | None
    language_id: UUID | None


@dataclass(frozen=True, slots=True)
class AccessReferences:
    """What the user's assignments refer to, resolved by id."""

    roles: Mapping[UUID, Role]
    projects: Mapping[UUID, Project]
    languages: Mapping[UUID, Language]

    def assignment(self, assignment: RoleAssignment) -> AssignmentResult | None:
        role = self.roles.get(assignment.role_id)
        if role is None:
            return None
        project = self.projects.get(assignment.project_id) if assignment.project_id else None
        language = self.languages.get(assignment.language_id) if assignment.language_id else None
        return AssignmentResult(
            assignment.id,
            RoleSummaryResult(role.id, role.name),
            None if project is None else ProjectRefResult(project.id, project.name),
            None
            if language is None
            else LanguageRefResult(language.id, language.code.value, language.name),
        )


def _grants(authorization: Authorization) -> tuple[GrantResult, ...]:
    return tuple(
        GrantResult(g.permission.value, g.project_id, g.language_id) for g in authorization.grants
    )


@dataclass(frozen=True, slots=True)
class UserResult:
    id: UUID
    email: str
    display_name: str
    is_active: bool
    assignments: tuple[AssignmentResult, ...]
    grants: tuple[GrantResult, ...]

    @classmethod
    def of(cls, user: User, references: AccessReferences) -> UserResult:
        assignments = tuple(
            result
            for assignment in user.assignments
            if (result := references.assignment(assignment)) is not None
        )
        grants = _grants(Authorization.of(user, references.roles))
        return cls(user.id, user.email, user.display_name, user.is_active, assignments, grants)


@dataclass(frozen=True, slots=True)
class CurrentUserResult:
    id: UUID
    email: str
    display_name: str
    authorization: Authorization

    @classmethod
    def of(cls, user: User, authorization: Authorization) -> CurrentUserResult:
        return cls(user.id, user.email, user.display_name, authorization)

    @property
    def permissions(self) -> tuple[str, ...]:
        """Every permission held in some scope, for the front to gate its UI."""
        return _codes(self.authorization.permissions)

    @property
    def grants(self) -> tuple[GrantResult, ...]:
        return _grants(self.authorization)

    def holds(self, permission: Permission) -> bool:
        return self.authorization.holds(permission)

    def authorize(
        self,
        permission: Permission,
        project_id: UUID | None = None,
        language_id: UUID | None = None,
    ) -> bool:
        return self.authorization.authorize(permission, project_id, language_id)

    def can_see(self, project_id: UUID) -> bool:
        return self.authorization.can_see(project_id)
