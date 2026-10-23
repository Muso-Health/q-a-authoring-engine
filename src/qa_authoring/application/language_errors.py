from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class LanguageNotFoundError(Exception):
    """Raised when the addressed language does not exist."""

    def __init__(self, language_id: UUID) -> None:
        super().__init__(f"language {language_id} not found")
        self.language_id = language_id


class LanguageCodeAlreadyExistsError(Exception):
    """Raised when registering a language whose code is already taken."""

    def __init__(self, code: str) -> None:
        super().__init__(f"language code {code!r} already exists")
        self.code = code
