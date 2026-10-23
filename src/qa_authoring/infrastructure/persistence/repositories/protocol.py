from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.project_errors import ProjectNotFoundError
from qa_authoring.application.protocol_errors import ProtocolHasThemesError
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.catalog import protocols

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


def _to_domain(row: Any) -> Protocol:
    return Protocol(row.id, row.project_id, row.name, row.description)


class PostgresProtocolRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, protocol: Protocol) -> None:
        try:
            await self._connection.execute(
                insert(protocols).values(
                    id=protocol.id,
                    project_id=protocol.project_id,
                    name=protocol.name,
                    description=protocol.description,
                )
            )
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise ProjectNotFoundError(protocol.project_id) from exc
            raise

    async def get(self, protocol_id: UUID) -> Protocol | None:
        row = (
            await self._connection.execute(select(protocols).where(protocols.c.id == protocol_id))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def list_by_project(self, project_id: UUID) -> tuple[Protocol, ...]:
        rows = await self._connection.execute(
            select(protocols)
            .where(protocols.c.project_id == project_id)
            .order_by(protocols.c.name, protocols.c.id)
        )
        return tuple(_to_domain(row) for row in rows)

    async def update(self, protocol: Protocol) -> None:
        await self._connection.execute(
            update(protocols)
            .where(protocols.c.id == protocol.id)
            .values(name=protocol.name, description=protocol.description)
        )

    async def delete(self, protocol_id: UUID) -> None:
        try:
            await self._connection.execute(delete(protocols).where(protocols.c.id == protocol_id))
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise ProtocolHasThemesError(protocol_id) from exc
            raise

    async def exists_for_project(self, project_id: UUID) -> bool:
        query = select(exists().where(protocols.c.project_id == project_id))
        return bool(await self._connection.scalar(query))
