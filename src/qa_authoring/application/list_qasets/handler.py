from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_response import QASetSummaryResult
from qa_authoring.application.theme_errors import ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.list_qasets.command import ListQASetsQuery
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class ListQASetsHandler:
    """The theme's QA sets, each summarised by its languages and their variant counts."""

    def __init__(self, qasets: QASetRepository, themes: ThemeRepository) -> None:
        self._qasets = qasets
        self._themes = themes

    async def __call__(self, query: ListQASetsQuery) -> tuple[QASetSummaryResult, ...]:
        if await self._themes.get(query.theme_id) is None:
            raise ThemeNotFoundError(query.theme_id)
        qasets = await self._qasets.list_by_theme(query.theme_id)
        return tuple(QASetSummaryResult.of(qaset) for qaset in qasets)
