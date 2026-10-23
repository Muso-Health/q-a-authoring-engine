from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from qa_authoring.domain.value_objects.naming import clean_description, clean_name

if TYPE_CHECKING:
    from uuid import UUID


class NamedEntity:
    """Identity plus the editable ``name`` / ``description`` pair shared by the catalog
    aggregates. Equality is by identity."""

    __slots__ = ("_description", "_id", "_name")

    subject: ClassVar[str]

    def __init__(self, entity_id: UUID, name: str, description: str | None) -> None:
        self._id = entity_id
        self._name = clean_name(name, subject=self.subject)
        self._description = clean_description(description)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str | None:
        return self._description

    def rename(self, name: str) -> None:
        self._name = clean_name(name, subject=self.subject)

    def describe(self, description: str | None) -> None:
        self._description = clean_description(description)

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id}, name={self._name!r})"
