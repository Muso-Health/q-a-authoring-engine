from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.language import Language
    from qa_authoring.domain.value_objects.language_code import LanguageCode


class LanguageRepository(Protocol):
    async def add(self, language: Language) -> None:
        """Insert a new language. Raises ``LanguageCodeAlreadyExistsError`` if the code is taken."""
        ...

    async def get(self, language_id: UUID) -> Language | None: ...

    async def find_by_code(self, code: LanguageCode) -> Language | None: ...

    async def list(self) -> tuple[Language, ...]:
        """Every language, ordered by code."""
        ...

    async def update(self, language: Language) -> None:
        """Persist the mutable attributes (the name) of an existing language."""
        ...

    async def delete(self, language_id: UUID) -> None: ...
