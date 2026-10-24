from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.qaset import AudioReference, QASet


class QASetRepository(Protocol):
    """Loads and saves the whole QASet aggregate (its answers and question variants included)."""

    async def add(self, qaset: QASet) -> None:
        """Raises ``ThemeNotFoundError`` / ``UnknownLanguageError`` on a dangling reference."""
        ...

    async def get(self, qaset_id: UUID) -> QASet | None: ...

    async def list_by_theme(self, theme_id: UUID) -> tuple[QASet, ...]: ...

    async def save(self, qaset: QASet) -> None:
        """Persist the aggregate's current answers and variants, replacing the stored ones."""
        ...

    async def delete(self, qaset_id: UUID) -> None:
        """Delete the QA set together with its answers and variants."""
        ...

    async def exists_for_theme(self, theme_id: UUID) -> bool: ...

    async def uses_language(self, language_id: UUID) -> bool: ...

    async def uses_intent(self, intent_id: UUID) -> bool: ...

    async def uses_category(self, category_id: UUID) -> bool: ...

    async def find_audio(self, audio_id: UUID) -> AudioReference | None: ...

    async def find_by_answer(self, answer_id: UUID) -> QASet | None: ...

    async def find_by_variant(self, variant_id: UUID) -> QASet | None: ...

    async def storage_uri_in_use(self, storage_uri: str) -> bool:
        """Whether any stored audio reference still points at this blob."""
        ...
