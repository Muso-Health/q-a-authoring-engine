from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.completeness_errors import NoDocumentationError
from qa_authoring.application.documentation_response import CompletenessResult
from qa_authoring.application.theme_errors import ThemeNotFoundError

if TYPE_CHECKING:
    from qa_authoring.application.analyze_theme_completeness.command import (
        AnalyzeThemeCompletenessQuery,
    )
    from qa_authoring.application.ports.completeness_analyzer import CompletenessAnalyzerPort
    from qa_authoring.application.ports.document_extraction import DocumentExtractionPort
    from qa_authoring.application.ports.documentation_repository import DocumentationRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.validation_support import BaseLanguageResolver


class AnalyzeThemeCompletenessHandler:
    """Which notions of a theme's documentation no answer covers yet, reasoned in the project's
    base language over that language's answers. Proposes only; nothing is saved."""

    def __init__(
        self,
        themes: ThemeRepository,
        base_language: BaseLanguageResolver,
        languages: LanguageRepository,
        documentation: DocumentationRepository,
        qasets: QASetRepository,
        extractor: DocumentExtractionPort,
        analyzer: CompletenessAnalyzerPort,
    ) -> None:
        self._themes = themes
        self._base_language = base_language
        self._languages = languages
        self._documentation = documentation
        self._qasets = qasets
        self._extractor = extractor
        self._analyzer = analyzer

    async def __call__(self, query: AnalyzeThemeCompletenessQuery) -> CompletenessResult:
        theme = await self._themes.get(query.theme_id)
        if theme is None:
            raise ThemeNotFoundError(query.theme_id)
        sections = []
        for document in await self._documentation.list_by_theme(theme.id):
            text = await self._extractor.extract(document)
            if text and text.strip():
                sections.append(f"## {document.filename}\n{text.strip()}")
        if not sections:
            raise NoDocumentationError(theme.id)
        base = await self._base_language.of_theme(theme.id)
        language = await self._languages.get(base)
        assert language is not None  # a project's base language is held by a RESTRICT foreign key
        answers = [
            qaset.presence(base).answer.text
            for qaset in await self._qasets.list_by_theme(theme.id)
            if base in {p.language_id for p in qaset.presences()}
        ]
        notions = await self._analyzer.analyze("\n\n".join(sections), answers, language)
        return CompletenessResult(notions)
