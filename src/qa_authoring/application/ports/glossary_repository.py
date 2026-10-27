from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.glossary import GlossaryStatus, GlossaryTerm


class GlossaryRepository(Protocol):
    async def add(self, term: GlossaryTerm) -> None:
        """Raises ``UnknownLanguageError`` if a form's language is not registered."""
        ...

    async def get(self, term_id: UUID) -> GlossaryTerm | None: ...

    async def get_for_update(self, term_id: UUID) -> GlossaryTerm | None:
        """``get``, locking the term until the transaction ends, so concurrent edits of one term
        apply one after the other."""
        ...

    async def save(self, term: GlossaryTerm) -> None:
        """Stores the term and exactly its forms. Raises ``UnknownLanguageError`` like ``add``."""
        ...

    async def active_with_forms_in(
        self, source_language_id: UUID, target_language_id: UUID
    ) -> tuple[GlossaryTerm, ...]:
        """The active terms with a form in both languages (with all their forms): the
        candidates for guiding a translation between them."""
        ...

    async def list(
        self, *, status: GlossaryStatus | None, search: str | None, limit: int, offset: int
    ) -> tuple[tuple[GlossaryTerm, ...], int]:
        """A page of terms ordered by label (case-insensitive), and the count of every match.
        ``status`` None means any; ``search`` matches inside the label or any form string,
        ignoring case and accents."""
        ...
