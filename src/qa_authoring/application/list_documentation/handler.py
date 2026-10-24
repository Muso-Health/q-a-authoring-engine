from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.documentation_response import DocumentationResult
from qa_authoring.application.theme_errors import ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.list_documentation.command import ListDocumentationQuery
    from qa_authoring.application.ports.documentation_repository import DocumentationRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository


class ListDocumentationHandler:
    def __init__(self, themes: ThemeRepository, documentation: DocumentationRepository) -> None:
        self._themes = themes
        self._documentation = documentation

    async def __call__(self, query: ListDocumentationQuery) -> tuple[DocumentationResult, ...]:
        if await self._themes.get(query.theme_id) is None:
            raise ThemeNotFoundError(query.theme_id)
        documents = await self._documentation.list_by_theme(query.theme_id)
        return tuple(DocumentationResult.of(d) for d in documents)
