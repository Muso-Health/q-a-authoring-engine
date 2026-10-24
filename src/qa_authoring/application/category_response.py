from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on a frozen result dataclass

if TYPE_CHECKING:
    from qa_authoring.domain.model.category import Category


@dataclass(frozen=True, slots=True)
class CategoryResult:
    id: UUID
    name: str

    @classmethod
    def of(cls, category: Category) -> CategoryResult:
        return cls(category.id, category.name)
