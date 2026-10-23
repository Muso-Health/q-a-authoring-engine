from __future__ import annotations

from typing import TYPE_CHECKING, Self

from qa_authoring.infrastructure.persistence.repositories.language import (
    PostgresLanguageRepository,
)

if TYPE_CHECKING:
    from types import TracebackType

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

    from qa_authoring.application.ports.language_repository import LanguageRepository


class SqlAlchemyUnitOfWork:
    """One connection and one transaction per use case; every repository is enlisted on it.
    Commits on a clean exit, rolls back on an exception."""

    languages: LanguageRepository

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None

    async def __aenter__(self) -> Self:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        self.languages = PostgresLanguageRepository(self._connection)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._connection is not None and self._transaction is not None
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self._connection.close()
