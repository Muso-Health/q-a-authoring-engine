from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.category_errors import CategoryNotFoundError
from qa_authoring.application.category_response import CategoryResult

if TYPE_CHECKING:
    from qa_authoring.application.get_category.command import GetCategoryQuery
    from qa_authoring.application.ports.category_repository import CategoryRepository


class GetCategoryHandler:
    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    async def __call__(self, query: GetCategoryQuery) -> CategoryResult:
        category = await self._categories.get(query.category_id)
        if category is None:
            raise CategoryNotFoundError(query.category_id)
        return CategoryResult.of(category)
