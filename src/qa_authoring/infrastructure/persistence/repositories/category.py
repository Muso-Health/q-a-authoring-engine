from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.category_errors import CategoryInUseError
from qa_authoring.domain.model.category import Category
from qa_authoring.domain.value_objects.naming import normalize_key
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.category import categories

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


def _to_domain(row: Any) -> Category:
    return Category(row.id, row.name)


class PostgresCategoryRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get_or_create(self, category: Category) -> tuple[Category, bool]:
        inserted = await self._connection.scalar(
            insert(categories)
            .values(id=category.id, name=category.name, key=category.key)
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(categories.c.id)
        )
        if inserted is not None:
            return category, True
        row = (
            await self._connection.execute(
                select(categories).where(categories.c.key == category.key)
            )
        ).one()
        return _to_domain(row), False

    async def get(self, category_id: UUID) -> Category | None:
        row = (
            await self._connection.execute(select(categories).where(categories.c.id == category_id))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def get_many(self, category_ids: set[UUID]) -> dict[UUID, Category]:
        rows = await self._connection.execute(
            select(categories).where(categories.c.id.in_(category_ids))
        )
        return {row.id: _to_domain(row) for row in rows}

    async def list(self, prefix: str | None = None) -> tuple[Category, ...]:
        query = select(categories).order_by(categories.c.key, categories.c.id)
        key = normalize_key(prefix or "")
        if key:
            query = query.where(categories.c.key.startswith(key, autoescape=True))
        return tuple(_to_domain(row) for row in await self._connection.execute(query))

    async def delete(self, category_id: UUID) -> None:
        try:
            await self._connection.execute(delete(categories).where(categories.c.id == category_id))
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise CategoryInUseError(category_id) from exc
            raise
