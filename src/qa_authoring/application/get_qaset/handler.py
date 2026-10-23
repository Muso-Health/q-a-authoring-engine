from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.qaset_loading import load_qaset
from qa_authoring.application.qaset_response import QASetResult

if TYPE_CHECKING:
    from qa_authoring.application.get_qaset.command import GetQASetQuery
    from qa_authoring.application.ports.qaset_repository import QASetRepository


class GetQASetHandler:
    """The full QA set, grouped by language."""

    def __init__(self, qasets: QASetRepository) -> None:
        self._qasets = qasets

    async def __call__(self, query: GetQASetQuery) -> QASetResult:
        return QASetResult.of(await load_qaset(self._qasets, query.qaset_id))
