from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003 — a field type on a frozen dataclass


@dataclass(frozen=True, slots=True)
class ListProjectsQuery:
    """``project_ids`` restricts the listing to those projects; None lists every project."""

    project_ids: frozenset[UUID] | None = None
