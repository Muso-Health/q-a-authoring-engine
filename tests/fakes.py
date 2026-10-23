from __future__ import annotations

from typing import TYPE_CHECKING, Self

from config.container import Container

if TYPE_CHECKING:
    from types import TracebackType
    from uuid import UUID

    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.domain.model.language import Language
    from qa_authoring.domain.value_objects.language_code import LanguageCode


class InMemoryLanguageRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Language] = {}

    async def add(self, language: Language) -> None:
        self.rows[language.id] = language

    async def get(self, language_id: UUID) -> Language | None:
        return self.rows.get(language_id)

    async def find_by_code(self, code: LanguageCode) -> Language | None:
        return next((row for row in self.rows.values() if row.code == code), None)

    async def list(self) -> tuple[Language, ...]:
        return tuple(sorted(self.rows.values(), key=lambda row: row.code.value))

    async def update(self, language: Language) -> None:
        self.rows[language.id] = language

    async def delete(self, language_id: UUID) -> None:
        self.rows.pop(language_id, None)


class InMemoryUnitOfWork:
    languages: LanguageRepository

    def __init__(self, languages: InMemoryLanguageRepository) -> None:
        self.languages = languages

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


def in_memory_container() -> tuple[Container, InMemoryLanguageRepository]:
    languages = InMemoryLanguageRepository()
    return Container(lambda: InMemoryUnitOfWork(languages)), languages
