from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.category_response import CategoryResult
from qa_authoring.domain.model.category import Category

if TYPE_CHECKING:
    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.register_category.command import RegisterCategoryCommand


class RegisterCategoryHandler:
    """Get-or-create by normalized name; the flag says whether the category was created."""

    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    async def __call__(self, command: RegisterCategoryCommand) -> tuple[CategoryResult, bool]:
        category, created = await self._categories.get_or_create(Category.register(command.name))
        return CategoryResult.of(category), created
