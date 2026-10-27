from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_errors import GlossaryTermNotFoundError
from qa_authoring.application.glossary_response import GlossaryTermResult

if TYPE_CHECKING:
    from qa_authoring.application.get_glossary_term.command import GetGlossaryTermQuery
    from qa_authoring.application.ports.glossary_repository import GlossaryRepository


class GetGlossaryTermHandler:
    def __init__(self, glossary: GlossaryRepository) -> None:
        self._glossary = glossary

    async def __call__(self, query: GetGlossaryTermQuery) -> GlossaryTermResult:
        term = await self._glossary.get(query.term_id)
        if term is None:
            raise GlossaryTermNotFoundError(query.term_id)
        return GlossaryTermResult.of(term)
