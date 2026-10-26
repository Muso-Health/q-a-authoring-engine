from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from qa_authoring.domain.model.permission import Permission, PermissionScope

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from uuid import UUID

    from qa_authoring.domain.model.role import Role
    from qa_authoring.domain.model.user import User


@dataclass(frozen=True, slots=True)
class Grant:
    """One permission within a scope, normalized to its permission's scope class: a global
    grant carries no scope and a project grant no language. Null means any."""

    permission: Permission
    project_id: UUID | None = None
    language_id: UUID | None = None

    @classmethod
    def scoped(
        cls, permission: Permission, project_id: UUID | None, language_id: UUID | None
    ) -> Grant:
        if permission.scope is PermissionScope.GLOBAL:
            return cls(permission)
        if permission.scope is PermissionScope.PROJECT:
            return cls(permission, project_id)
        return cls(permission, project_id, language_id)

    def covers(self, project_id: UUID | None, language_id: UUID | None) -> bool:
        if self.project_id is not None and self.project_id != project_id:
            return False
        return self.language_id is None or self.language_id == language_id


class Authorization:
    """What one user may do and see, from their scoped role assignments."""

    __slots__ = ("_grants", "_visible")

    def __init__(
        self, grants: Iterable[Grant], visible_project_ids: frozenset[UUID] | None
    ) -> None:
        self._grants = frozenset(grants)
        self._visible = visible_project_ids

    @classmethod
    def of(cls, user: User, roles: Mapping[UUID, Role]) -> Authorization:
        """``roles`` resolves the user's role ids; an inactive user holds and sees nothing."""
        if not user.is_active:
            return cls((), frozenset())
        grants = {
            Grant.scoped(permission, a.project_id, a.language_id)
            for a in user.assignments
            if a.role_id in roles
            for permission in roles[a.role_id].permissions
        }
        projects = {a.project_id for a in user.assignments}
        visible = None if None in projects else frozenset(p for p in projects if p is not None)
        return cls(grants, visible)

    @property
    def grants(self) -> tuple[Grant, ...]:
        return tuple(
            sorted(
                self._grants, key=lambda g: (g.permission, str(g.project_id), str(g.language_id))
            )
        )

    @property
    def permissions(self) -> frozenset[Permission]:
        """Every permission held in some scope."""
        return frozenset(g.permission for g in self._grants)

    @property
    def visible_project_ids(self) -> frozenset[UUID] | None:
        """The projects any assignment covers; None when one covers every project."""
        return self._visible

    def holds(self, permission: Permission) -> bool:
        return any(g.permission is permission for g in self._grants)

    def authorize(
        self,
        permission: Permission,
        project_id: UUID | None = None,
        language_id: UUID | None = None,
    ) -> bool:
        return any(
            g.permission is permission and g.covers(project_id, language_id) for g in self._grants
        )

    def can_see(self, project_id: UUID) -> bool:
        return self._visible is None or project_id in self._visible
