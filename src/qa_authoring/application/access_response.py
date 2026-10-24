from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from qa_authoring.domain.model.permission import Permission
    from qa_authoring.domain.model.role import Role
    from qa_authoring.domain.model.user import User


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
class UserResult:
    id: UUID
    email: str
    display_name: str
    is_active: bool
    roles: tuple[RoleSummaryResult, ...]

    @classmethod
    def of(cls, user: User, roles: Mapping[UUID, Role]) -> UserResult:
        """``roles`` resolves the user's role ids to their roles."""
        summaries = tuple(
            RoleSummaryResult(role_id, roles[role_id].name)
            for role_id in user.role_ids
            if role_id in roles
        )
        return cls(user.id, user.email, user.display_name, user.is_active, summaries)


@dataclass(frozen=True, slots=True)
class CurrentUserResult:
    id: UUID
    email: str
    display_name: str
    permissions: tuple[str, ...]

    @classmethod
    def of(cls, user: User, permissions: Iterable[Permission]) -> CurrentUserResult:
        return cls(user.id, user.email, user.display_name, _codes(permissions))

    def holds(self, permission: Permission) -> bool:
        return permission.value in self.permissions
