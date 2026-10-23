from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from types import TracebackType

    from qa_authoring.application.ports.language_repository import LanguageRepository


class UnitOfWork(Protocol):
    """One transaction: the repositories enlisted on it commit together on a clean exit and roll
    back together on an exception."""

    languages: LanguageRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
