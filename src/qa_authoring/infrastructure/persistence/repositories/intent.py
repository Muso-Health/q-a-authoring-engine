from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.intent_errors import IntentInUseError
from qa_authoring.domain.model.intent import Intent, normalize_intent_text
from qa_authoring.infrastructure.persistence.repositories._integrity import (
    FOREIGN_KEY_VIOLATION,
    sqlstate,
)
from qa_authoring.infrastructure.persistence.schema.intent import intents

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection


def _to_domain(row: Any) -> Intent:
    return Intent(row.id, row.text)


class PostgresIntentRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get_or_create(self, intent: Intent) -> tuple[Intent, bool]:
        inserted = await self._connection.scalar(
            insert(intents)
            .values(id=intent.id, text=intent.text, key=intent.key)
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(intents.c.id)
        )
        if inserted is not None:
            return intent, True
        row = (
            await self._connection.execute(select(intents).where(intents.c.key == intent.key))
        ).one()
        return _to_domain(row), False

    async def get(self, intent_id: UUID) -> Intent | None:
        row = (
            await self._connection.execute(select(intents).where(intents.c.id == intent_id))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def get_many(self, intent_ids: set[UUID]) -> dict[UUID, Intent]:
        rows = await self._connection.execute(select(intents).where(intents.c.id.in_(intent_ids)))
        return {row.id: _to_domain(row) for row in rows}

    async def list(self, prefix: str | None = None) -> tuple[Intent, ...]:
        query = select(intents).order_by(intents.c.key, intents.c.id)
        key = normalize_intent_text(prefix or "")
        if key:
            query = query.where(intents.c.key.startswith(key, autoescape=True))
        return tuple(_to_domain(row) for row in await self._connection.execute(query))

    async def delete(self, intent_id: UUID) -> None:
        try:
            await self._connection.execute(delete(intents).where(intents.c.id == intent_id))
        except IntegrityError as exc:
            if sqlstate(exc) == FOREIGN_KEY_VIOLATION:
                raise IntentInUseError(intent_id) from exc
            raise
