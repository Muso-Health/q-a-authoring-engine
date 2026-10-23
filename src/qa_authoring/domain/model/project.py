from __future__ import annotations

from uuid import UUID, uuid4

from qa_authoring.domain.model._named_entity import NamedEntity


class Project(NamedEntity):
    """The root of a Q&A corpus. Its base language is fixed at creation."""

    __slots__ = ("_base_language_id",)
    subject = "project"

    def __init__(
        self, project_id: UUID, name: str, description: str | None, base_language_id: UUID
    ) -> None:
        super().__init__(project_id, name, description)
        self._base_language_id = base_language_id

    @classmethod
    def create(
        cls, *, name: str, base_language_id: UUID, description: str | None = None
    ) -> Project:
        return cls(uuid4(), name, description, base_language_id)

    @property
    def base_language_id(self) -> UUID:
        return self._base_language_id
