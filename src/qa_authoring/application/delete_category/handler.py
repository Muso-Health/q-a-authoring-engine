from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.category_errors import CategoryInUseError, CategoryNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.delete_category.command import DeleteCategoryCommand
    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class DeleteCategoryHandler:
    """Guarded delete: refused while any QA set has the category attached."""

    def __init__(self, categories: CategoryRepository, qasets: QASetRepository) -> None:
        self._categories = categories
        self._qasets = qasets

    async def __call__(self, command: DeleteCategoryCommand) -> None:
        if await self._categories.get(command.category_id) is None:
            raise CategoryNotFoundError(command.category_id)
        if await self._qasets.uses_category(command.category_id):
            raise CategoryInUseError(command.category_id)
        await self._categories.delete(command.category_id)
