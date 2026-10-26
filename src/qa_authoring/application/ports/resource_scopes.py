from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


class ResourceKind(StrEnum):
    PROJECT = "project"
    PROTOCOL = "protocol"
    THEME = "theme"
    QASET = "qaset"
    ANSWER = "answer"
    VARIANT = "variant"
    AUDIO = "audio"
    DOCUMENTATION = "documentation"


@dataclass(frozen=True, slots=True)
class ResourceScope:
    """The project a resource belongs to and, for an answer, variant or audio, its language."""

    project_id: UUID
    language_id: UUID | None = None


class ResourceScopes(Protocol):
    async def resolve(self, kind: ResourceKind, resource_id: UUID) -> ResourceScope | None:
        """None when the resource does not exist."""
        ...
