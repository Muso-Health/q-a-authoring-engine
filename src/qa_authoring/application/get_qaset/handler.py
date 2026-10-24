from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import category_names, intent_texts, load_qaset
from qa_authoring.application.qaset_response import QASetResult

if TYPE_CHECKING:
    from qa_authoring.application.get_qaset.command import GetQASetQuery
    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class GetQASetHandler:
    """The full QA set, grouped by language."""

    def __init__(
        self,
        qasets: QASetRepository,
        intents: IntentRepository,
        categories: CategoryRepository,
    ) -> None:
        self._qasets = qasets
        self._intents = intents
        self._categories = categories

    async def __call__(self, query: GetQASetQuery) -> QASetResult:
        qaset = await load_qaset(self._qasets, query.qaset_id)
        return QASetResult.of(
            qaset,
            await intent_texts(self._intents, qaset),
            await category_names(self._categories, qaset),
        )
