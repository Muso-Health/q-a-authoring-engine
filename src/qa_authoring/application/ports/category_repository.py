from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from qa_authoring.domain.model.category import Category


class CategoryRepository(Protocol):
    async def get_or_create(self, category: Category) -> tuple[Category, bool]:
        """The stored category with the same normalized name, or ``category`` once inserted; the
        flag says whether it was created. Safe against a concurrent registration of the same
        name."""
        ...

    async def get(self, category_id: UUID) -> Category | None: ...

    async def get_many(self, category_ids: set[UUID]) -> dict[UUID, Category]:
        """The known categories among ``category_ids``, keyed by id."""
        ...

    async def list(self, prefix: str | None = None) -> tuple[Category, ...]:
        """Ordered by normalized name; ``prefix`` matches the start of the normalized name."""
        ...

    async def delete(self, category_id: UUID) -> None:
        """Raises ``CategoryInUseError`` if a QA set still references it."""
        ...
