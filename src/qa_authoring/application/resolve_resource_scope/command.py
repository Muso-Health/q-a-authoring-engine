from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass

from qa_authoring.application.ports.resource_scopes import ResourceKind  # noqa: TC001 — a field


@dataclass(frozen=True, slots=True)
class ResolveResourceScopeQuery:
    kind: ResourceKind
    resource_id: UUID
