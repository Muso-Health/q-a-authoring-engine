from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.role_errors import RoleInUseError, RoleNameExistsError
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.role import Role
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    UNIQUE_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.access import role_permissions, roles

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresRoleRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, role: Role) -> None:
        try:
            await self._connection.execute(
                insert(roles).values(id=role.id, name=role.name, key=role.key)
            )
        except IntegrityError as exc:
            if sqlstate(exc) == UNIQUE_VIOLATION:
                raise RoleNameExistsError(role.name) from exc
            raise
        await self._insert_permissions(role)

    async def get(self, role_id: UUID) -> Role | None:
        found = await self._load(select(roles).where(roles.c.id == role_id))
        return found[0] if found else None

    async def get_many(self, role_ids: set[UUID]) -> dict[UUID, Role]:
        if not role_ids:
            return {}
        return {r.id: r for r in await self._load(select(roles).where(roles.c.id.in_(role_ids)))}

    async def find_by_key(self, key: str) -> Role | None:
        found = await self._load(select(roles).where(roles.c.key == key))
        return found[0] if found else None

    async def list(self) -> tuple[Role, ...]:
        return await self._load(select(roles).order_by(roles.c.key))

    async def update(self, role: Role) -> None:
        try:
            await self._connection.execute(
                update(roles).where(roles.c.id == role.id).values(name=role.name, key=role.key)
            )
        except IntegrityError as exc:
            if sqlstate(exc) == UNIQUE_VIOLATION:
                raise RoleNameExistsError(role.name) from exc
            raise
        await self._connection.execute(
            delete(role_permissions).where(role_permissions.c.role_id == role.id)
        )
        await self._insert_permissions(role)

    async def delete(self, role_id: UUID) -> None:
        try:
            await self._connection.execute(delete(roles).where(roles.c.id == role_id))
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise RoleInUseError(role_id) from exc
            raise

    async def _insert_permissions(self, role: Role) -> None:
        if role.permissions:
            await self._connection.execute(
                insert(role_permissions),
                [{"role_id": role.id, "permission_code": p.value} for p in role.permissions],
            )

    async def _load(self, query: Select[Any]) -> tuple[Role, ...]:
        rows = (await self._connection.execute(query)).all()
        if not rows:
            return ()
        codes: defaultdict[UUID, list[Permission]] = defaultdict(list)
        for row in await self._connection.execute(
            select(role_permissions).where(role_permissions.c.role_id.in_([r.id for r in rows]))
        ):
            # Codes outside the catalogue (removed from the enum) are ignored, never granted.
            if row.permission_code in Permission._value2member_map_:
                codes[row.role_id].append(Permission(row.permission_code))
        return tuple(Role(row.id, row.name, codes[row.id]) for row in rows)
