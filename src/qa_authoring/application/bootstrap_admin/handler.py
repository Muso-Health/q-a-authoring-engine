from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.role import Role
from qa_authoring.domain.model.user import User

if TYPE_CHECKING:
    from qa_authoring.application.bootstrap_admin.command import BootstrapAdminCommand
    from qa_authoring.application.ports.role_repository import RoleRepository
    from qa_authoring.application.ports.user_repository import UserRepository

ADMIN_ROLE_NAME = "admin"


class BootstrapAdminHandler:
    """Idempotently ensure an ``admin`` role holding every permission, and an active user with
    ``email`` holding it globally (any project, any language) — the way in when no one has access
    yet. Safe to run on every start; it also repairs the admin role after the catalogue grows."""

    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def __call__(self, command: BootstrapAdminCommand) -> None:
        everything = frozenset(Permission)
        role = await self._roles.find_by_key(ADMIN_ROLE_NAME)
        if role is None:
            role = Role.create(name=ADMIN_ROLE_NAME, permissions=everything)
            await self._roles.add(role)
        elif role.permissions != everything:
            role.replace_permissions(everything)
            await self._roles.update(role)

        user = await self._users.find_by_email(command.email)
        if user is None:
            user = User.create(email=command.email, display_name=command.email.strip())
            user.assign(role.id)
            await self._users.add(user)
            return
        _, assigned = user.assign(role.id)
        if assigned or not user.is_active:
            user.set_active(True)
            await self._users.update(user)
