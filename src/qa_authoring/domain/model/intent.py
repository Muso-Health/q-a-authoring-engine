from __future__ import annotations

from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_text


def normalize_intent_text(text: str) -> str:
    """The uniqueness key: trimmed, inner whitespace collapsed, lowercased."""
    return " ".join(text.split()).lower()


class Intent:
    """A language-neutral intent from the global catalogue, unique by its normalized text."""

    __slots__ = ("_id", "_text")

    def __init__(self, intent_id: UUID, text: str) -> None:
        self._id = intent_id
        self._text = clean_text(text, subject="intent")

    @classmethod
    def register(cls, text: str) -> Intent:
        return cls(uuid4(), text)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def text(self) -> str:
        return self._text

    @property
    def key(self) -> str:
        return normalize_intent_text(self._text)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Intent) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Intent(id={self._id}, text={self._text!r})"
