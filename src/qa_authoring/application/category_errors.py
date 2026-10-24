from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class CategoryNotFoundError(Exception):
    def __init__(self, category_id: UUID) -> None:
        super().__init__(f"category {category_id} not found")
        self.category_id = category_id


class CategoryInUseError(Exception):
    """Raised when deleting a category still attached to a QA set."""

    def __init__(self, category_id: UUID) -> None:
        super().__init__(f"category {category_id} is attached to QA sets")
        self.category_id = category_id
