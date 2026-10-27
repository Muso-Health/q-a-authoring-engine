from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.glossary_response import GlossaryTermPage, GlossaryTermResult
from qa_authoring.application.list_glossary_terms.command import MAX_GLOSSARY_PAGE

if TYPE_CHECKING:
    from qa_authoring.application.list_glossary_terms.command import ListGlossaryTermsQuery
    from qa_authoring.application.ports.glossary_repository import GlossaryRepository


class ListGlossaryTermsHandler:
    """Terms ordered by label, filtered by status and an optional search; a limit above
    ``MAX_GLOSSARY_PAGE`` is lowered to it."""

    def __init__(self, glossary: GlossaryRepository) -> None:
        self._glossary = glossary

    async def __call__(self, query: ListGlossaryTermsQuery) -> GlossaryTermPage:
        search = (query.search or "").strip() or None
        terms, total = await self._glossary.list(
            status=query.status,
            search=search,
            limit=max(1, min(query.limit, MAX_GLOSSARY_PAGE)),
            offset=max(0, query.offset),
        )
        return GlossaryTermPage(tuple(GlossaryTermResult.of(t) for t in terms), total)
