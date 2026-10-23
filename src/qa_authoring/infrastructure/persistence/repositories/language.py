from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.language_errors import LanguageCodeAlreadyExistsError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.schema.language import languages

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncConnection

_UNIQUE_VIOLATION = "23505"


def _to_domain(row: Any) -> Language:
    return Language(row.id, LanguageCode(row.code), row.name)


class PostgresLanguageRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, language: Language) -> None:
        try:
            await self._connection.execute(
                insert(languages).values(
                    id=language.id, code=language.code.value, name=language.name
                )
            )
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise LanguageCodeAlreadyExistsError(language.code.value) from exc
            raise

    async def get(self, language_id: UUID) -> Language | None:
        row = (
            await self._connection.execute(select(languages).where(languages.c.id == language_id))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def find_by_code(self, code: LanguageCode) -> Language | None:
        row = (
            await self._connection.execute(select(languages).where(languages.c.code == code.value))
        ).one_or_none()
        return None if row is None else _to_domain(row)

    async def list(self) -> tuple[Language, ...]:
        rows = await self._connection.execute(select(languages).order_by(languages.c.code))
        return tuple(_to_domain(row) for row in rows)

    async def update(self, language: Language) -> None:
        await self._connection.execute(
            update(languages).where(languages.c.id == language.id).values(name=language.name)
        )

    async def delete(self, language_id: UUID) -> None:
        await self._connection.execute(delete(languages).where(languages.c.id == language_id))
