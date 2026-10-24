from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, insert, select

from qa_authoring.domain.model.documentation import Documentation
from qa_authoring.infrastructure.persistence.schema.documentation import documentation

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = (
    "id",
    "theme_id",
    "filename",
    "mime_type",
    "size_bytes",
    "checksum_sha256",
    "storage_uri",
    "created_at",
)


def _to_domain(row: Any) -> Documentation:
    return Documentation(**{column: getattr(row, column) for column in _COLUMNS})


class PostgresDocumentationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, document: Documentation) -> None:
        await self._connection.execute(
            insert(documentation).values(**{c: getattr(document, c) for c in _COLUMNS})
        )

    async def get(self, documentation_id: UUID) -> Documentation | None:
        row = (
            await self._connection.execute(
                select(documentation).where(documentation.c.id == documentation_id)
            )
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def list_by_theme(self, theme_id: UUID) -> tuple[Documentation, ...]:
        rows = await self._connection.execute(
            select(documentation)
            .where(documentation.c.theme_id == theme_id)
            .order_by(documentation.c.created_at, documentation.c.id)
        )
        return tuple(_to_domain(row) for row in rows)

    async def delete(self, documentation_id: UUID) -> None:
        await self._connection.execute(
            delete(documentation).where(documentation.c.id == documentation_id)
        )

    async def storage_uri_in_use(self, storage_uri: str) -> bool:
        query = select(exists().where(documentation.c.storage_uri == storage_uri))
        return bool(await self._connection.scalar(query))
