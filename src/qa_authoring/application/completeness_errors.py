from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class NoDocumentationError(Exception):
    """Raised when a theme has no documentation whose text can be read."""

    def __init__(self, theme_id: UUID) -> None:
        super().__init__(f"theme {theme_id} has no documentation with readable text")
        self.theme_id = theme_id
