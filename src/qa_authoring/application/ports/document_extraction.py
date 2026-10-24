from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.domain.model.documentation import Documentation


class DocumentExtractionPort(Protocol):
    async def extract(self, documentation: Documentation) -> str | None:
        """The document's text, or None when it holds none this adapter can read (media, an
        unreadable or empty file)."""
        ...
