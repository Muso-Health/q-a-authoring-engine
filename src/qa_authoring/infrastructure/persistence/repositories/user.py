from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.user_errors import EmailAlreadyExistsError
from qa_authoring.domain.model.user import User
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    UNIQUE_VIOLATION,
    constraint_name,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.access import user_roles, users

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresUserRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, user: User) -> None:
        try:
            await self._connection.execute(insert(users).values(**self._row(user)))
        except IntegrityError as exc:
            if sqlstate(exc) == UNIQUE_VIOLATION and constraint_name(exc) == "uq_users_email_lower":
                raise EmailAlreadyExistsError(user.email) from exc
            raise
        await self._insert_roles(user, user.role_ids)

    async def get(self, user_id: UUID) -> User | None:
        found = await self._load(select(users).where(users.c.id == user_id))
        return found[0] if found else None

    async def find_by_email(self, email: str) -> User | None:
        found = await self._load(
            select(users).where(func.lower(users.c.email) == email.strip().lower())
        )
        return found[0] if found else None

    async def list(self) -> tuple[User, ...]:
        return await self._load(select(users).order_by(users.c.email))

    async def update(self, user: User) -> None:
        values = self._row(user)
        del values["id"]
        await self._connection.execute(update(users).where(users.c.id == user.id).values(**values))
        stored: set[UUID] = set(
            await self._connection.scalars(
                select(user_roles.c.role_id).where(user_roles.c.user_id == user.id)
            )
        )
        removed = stored - set(user.role_ids)
        if removed:
            await self._connection.execute(
                delete(user_roles).where(
                    user_roles.c.user_id == user.id, user_roles.c.role_id.in_(removed)
                )
            )
        await self._insert_roles(user, [r for r in user.role_ids if r not in stored])

    async def uses_role(self, role_id: UUID) -> bool:
        query = select(exists().where(user_roles.c.role_id == role_id))
        return bool(await self._connection.scalar(query))

    @staticmethod
    def _row(user: User) -> dict[str, object]:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "subject": user.subject,
            "is_active": user.is_active,
        }

    async def _insert_roles(self, user: User, role_ids: Sequence[UUID]) -> None:
        # One by one so created_at follows assignment order.
        for role_id in role_ids:
            await self._connection.execute(
                insert(user_roles).values(user_id=user.id, role_id=role_id)
            )

    async def _load(self, query: Select[Any]) -> tuple[User, ...]:
        rows = (await self._connection.execute(query)).all()
        if not rows:
            return ()
        role_ids: defaultdict[UUID, list[UUID]] = defaultdict(list)
        for row in await self._connection.execute(
            select(user_roles.c.user_id, user_roles.c.role_id)
            .where(user_roles.c.user_id.in_([r.id for r in rows]))
            .order_by(user_roles.c.created_at, user_roles.c.role_id)
        ):
            role_ids[row.user_id].append(row.role_id)
        return tuple(
            User(
                row.id,
                row.email,
                row.display_name,
                subject=row.subject,
                is_active=row.is_active,
                role_ids=role_ids[row.id],
            )
            for row in rows
        )
