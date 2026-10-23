from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class QASetNotFoundError(Exception):
    def __init__(self, qaset_id: UUID) -> None:
        super().__init__(f"QA set {qaset_id} not found")
        self.qaset_id = qaset_id


class UnknownLanguageError(Exception):
    """Raised when a QA set references a language that is not registered. ``language_id`` is
    None when the database rejected it without saying which one."""

    def __init__(self, language_id: UUID | None) -> None:
        subject = "a language" if language_id is None else f"language {language_id}"
        super().__init__(f"{subject} is not registered")
        self.language_id = language_id
