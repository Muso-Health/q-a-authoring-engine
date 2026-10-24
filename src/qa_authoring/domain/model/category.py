from __future__ import annotations

from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_name, normalize_key


class Category:
    """A language-neutral category from the global catalogue, unique by its normalized name."""

    __slots__ = ("_id", "_name")

    def __init__(self, category_id: UUID, name: str) -> None:
        self._id = category_id
        self._name = clean_name(name, subject="category")

    @classmethod
    def register(cls, name: str) -> Category:
        return cls(uuid4(), name)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def key(self) -> str:
        return normalize_key(self._name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Category) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Category(id={self._id}, name={self._name!r})"
