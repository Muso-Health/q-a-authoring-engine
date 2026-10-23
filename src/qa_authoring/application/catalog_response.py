from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

if TYPE_CHECKING:
    from qa_authoring.domain.model.project import Project
    from qa_authoring.domain.model.protocol import Protocol
    from qa_authoring.domain.model.theme import Theme


@dataclass(frozen=True, slots=True)
class ProjectResult:
    id: UUID
    name: str
    description: str | None
    base_language_id: UUID

    @classmethod
    def of(cls, project: Project) -> ProjectResult:
        return cls(project.id, project.name, project.description, project.base_language_id)


@dataclass(frozen=True, slots=True)
class ProtocolResult:
    id: UUID
    project_id: UUID
    name: str
    description: str | None

    @classmethod
    def of(cls, protocol: Protocol) -> ProtocolResult:
        return cls(protocol.id, protocol.project_id, protocol.name, protocol.description)


@dataclass(frozen=True, slots=True)
class ThemeResult:
    id: UUID
    protocol_id: UUID
    name: str
    description: str | None

    @classmethod
    def of(cls, theme: Theme) -> ThemeResult:
        return cls(theme.id, theme.protocol_id, theme.name, theme.description)
