from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset

if TYPE_CHECKING:
    from qa_authoring.application.get_qaset.command import GetQASetQuery
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.qaset_response import QASetResult
    from qa_authoring.application.qaset_views import QASetViews


class GetQASetHandler:
    """The full QA set, grouped by language, with current validation states."""

    def __init__(self, qasets: QASetRepository, views: QASetViews) -> None:
        self._qasets = qasets
        self._views = views

    async def __call__(self, query: GetQASetQuery) -> QASetResult:
        return await self._views.qaset(await load_qaset(self._qasets, query.qaset_id))
