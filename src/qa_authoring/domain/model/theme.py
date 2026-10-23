from __future__ import annotations

from uuid import UUID, uuid4

from qa_authoring.domain.model._named_entity import NamedEntity


class Theme(NamedEntity):
    """A theme within a protocol."""

    __slots__ = ("_protocol_id",)
    subject = "theme"

    def __init__(
        self, theme_id: UUID, protocol_id: UUID, name: str, description: str | None
    ) -> None:
        super().__init__(theme_id, name, description)
        self._protocol_id = protocol_id

    @classmethod
    def create(cls, *, protocol_id: UUID, name: str, description: str | None = None) -> Theme:
        return cls(uuid4(), protocol_id, name, description)

    @property
    def protocol_id(self) -> UUID:
        return self._protocol_id
