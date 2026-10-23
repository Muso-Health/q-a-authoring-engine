from __future__ import annotations

from uuid import UUID, uuid4

from qa_authoring.domain.model._named_entity import NamedEntity


class Protocol(NamedEntity):
    """A clinical protocol within a project."""

    __slots__ = ("_project_id",)
    subject = "protocol"

    def __init__(
        self, protocol_id: UUID, project_id: UUID, name: str, description: str | None
    ) -> None:
        super().__init__(protocol_id, name, description)
        self._project_id = project_id

    @classmethod
    def create(cls, *, project_id: UUID, name: str, description: str | None = None) -> Protocol:
        return cls(uuid4(), project_id, name, description)

    @property
    def project_id(self) -> UUID:
        return self._project_id
