from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.category_response import CategoryResult

if TYPE_CHECKING:
    from qa_authoring.application.list_categories.command import ListCategoriesQuery
    from qa_authoring.application.ports.category_repository import CategoryRepository


class ListCategoriesHandler:
    """The catalogue, optionally narrowed to categories whose normalized name starts with a
    prefix."""

    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    async def __call__(self, query: ListCategoriesQuery) -> tuple[CategoryResult, ...]:
        return tuple(CategoryResult.of(c) for c in await self._categories.list(query.prefix))
