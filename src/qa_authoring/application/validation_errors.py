from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class NoBaseLanguagePresenceError(Exception):
    """Raised when clinically validating a QA set with no answer in its project's base language."""

    def __init__(self, qaset_id: UUID) -> None:
        super().__init__(f"QA set {qaset_id} has no answer in its project's base language")
        self.qaset_id = qaset_id


class NotATranslationError(Exception):
    """Raised when validating a base-language item as a translation."""

    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"{item_id} is in the project's base language, so not a translation")
        self.item_id = item_id
