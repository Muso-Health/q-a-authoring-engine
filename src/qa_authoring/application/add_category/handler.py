from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.category_errors import CategoryNotFoundError
from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.add_category.command import AddCategoryCommand
    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_response import QASetResult
    from qa_authoring.application.qaset_views import QASetViews


class AddCategoryHandler:
    """Attach a catalogue category to the whole QA set. Idempotent: the flag says whether the
    attachment was created."""

    def __init__(
        self, qasets: QASetRepository, categories: CategoryRepository, views: QASetViews
    ) -> None:
        self._qasets = qasets
        self._categories = categories
        self._views = views

    async def __call__(self, command: AddCategoryCommand) -> tuple[QASetResult, bool]:
        qaset = await load_qaset(self._qasets, command.qaset_id)
        if await self._categories.get(command.category_id) is None:
            raise CategoryNotFoundError(command.category_id)
        created = qaset.add_category(command.category_id)
        if created:
            await self._qasets.save(qaset)
        return await self._views.qaset(qaset), created
