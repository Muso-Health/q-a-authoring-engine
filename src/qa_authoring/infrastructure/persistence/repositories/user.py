from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.user_errors import EmailAlreadyExistsError
from qa_authoring.domain.model.user import RoleAssignment, User
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    UNIQUE_VIOLATION,
    constraint_name,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.access import user_role_assignments, users

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
        await self._insert_assignments(user, user.assignments)

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
        assignments = user_role_assignments
        stored: set[UUID] = set(
            await self._connection.scalars(
                select(assignments.c.id).where(assignments.c.user_id == user.id)
            )
        )
        removed = stored - {a.id for a in user.assignments}
        if removed:
            await self._connection.execute(
                delete(assignments).where(
                    assignments.c.user_id == user.id, assignments.c.id.in_(removed)
                )
            )
        await self._insert_assignments(user, [a for a in user.assignments if a.id not in stored])

    async def uses_role(self, role_id: UUID) -> bool:
        query = select(exists().where(user_role_assignments.c.role_id == role_id))
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

    async def _insert_assignments(self, user: User, assignments: Sequence[RoleAssignment]) -> None:
        # One by one so created_at follows assignment order.
        for a in assignments:
            await self._connection.execute(
                insert(user_role_assignments).values(
                    id=a.id,
                    user_id=user.id,
                    role_id=a.role_id,
                    project_id=a.project_id,
                    language_id=a.language_id,
                )
            )

    async def _load(self, query: Select[Any]) -> tuple[User, ...]:
        rows = (await self._connection.execute(query)).all()
        if not rows:
            return ()
        table = user_role_assignments
        assignments: defaultdict[UUID, list[RoleAssignment]] = defaultdict(list)
        for row in await self._connection.execute(
            select(table)
            .where(table.c.user_id.in_([r.id for r in rows]))
            .order_by(table.c.created_at, table.c.id)
        ):
            assignments[row.user_id].append(
                RoleAssignment(row.role_id, row.project_id, row.language_id, row.id)
            )
        return tuple(
            User(
                row.id,
                row.email,
                row.display_name,
                subject=row.subject,
                is_active=row.is_active,
                assignments=assignments[row.id],
            )
            for row in rows
        )
