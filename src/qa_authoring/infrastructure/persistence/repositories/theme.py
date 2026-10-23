from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.protocol_errors import ProtocolNotFoundError
from qa_authoring.domain.model.theme import Theme
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.catalog import themes

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


def _to_domain(row: Any) -> Theme:
    return Theme(row.id, row.protocol_id, row.name, row.description)


class PostgresThemeRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, theme: Theme) -> None:
        try:
            await self._connection.execute(
                insert(themes).values(
                    id=theme.id,
                    protocol_id=theme.protocol_id,
                    name=theme.name,
                    description=theme.description,
                )
            )
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise ProtocolNotFoundError(theme.protocol_id) from exc
            raise

    async def get(self, theme_id: UUID) -> Theme | None:
        row = (
            await self._connection.execute(select(themes).where(themes.c.id == theme_id))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def list_by_protocol(self, protocol_id: UUID) -> tuple[Theme, ...]:
        rows = await self._connection.execute(
            select(themes)
            .where(themes.c.protocol_id == protocol_id)
            .order_by(themes.c.name, themes.c.id)
        )
        return tuple(_to_domain(row) for row in rows)

    async def update(self, theme: Theme) -> None:
        await self._connection.execute(
            update(themes)
            .where(themes.c.id == theme.id)
            .values(name=theme.name, description=theme.description)
        )

    async def delete(self, theme_id: UUID) -> None:
        await self._connection.execute(delete(themes).where(themes.c.id == theme_id))

    async def exists_for_protocol(self, protocol_id: UUID) -> bool:
        query = select(exists().where(themes.c.protocol_id == protocol_id))
        return bool(await self._connection.scalar(query))
