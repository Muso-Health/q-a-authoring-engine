from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from qa_authoring.domain.value_objects.language_code import LanguageCode


class InvalidLanguageNameError(ValueError):
    """Raised when a language name is blank."""


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidLanguageNameError("language name must not be blank")
    return cleaned


class Language:
    """A language content can be authored in. Identified by a surrogate ``id``; ``code`` is unique
    and immutable once registered, ``name`` is the only mutable attribute."""

    __slots__ = ("_code", "_id", "_name")

    def __init__(self, language_id: UUID, code: LanguageCode, name: str) -> None:
        self._id = language_id
        self._code = code
        self._name = _clean_name(name)

    @classmethod
    def register(cls, code: LanguageCode, name: str) -> Language:
        return cls(uuid4(), code, name)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def code(self) -> LanguageCode:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    def rename(self, name: str) -> None:
        self._name = _clean_name(name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Language) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Language(id={self._id}, code={self._code.value!r}, name={self._name!r})"
