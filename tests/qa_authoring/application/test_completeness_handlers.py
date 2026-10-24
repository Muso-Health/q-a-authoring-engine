from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.analyze_theme_completeness.command import (
    AnalyzeThemeCompletenessQuery,
)
from qa_authoring.application.analyze_theme_completeness.handler import (
    AnalyzeThemeCompletenessHandler,
)
from qa_authoring.application.completeness_errors import NoDocumentationError
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.application.validation_support import BaseLanguageResolver
from qa_authoring.domain.model.documentation import Documentation
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from tests.fakes import NOW, FakeExtractor, InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence


class FakeAnalyzer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], str]] = []

    async def analyze(
        self, documentation: str, answers: Sequence[str], language: Language
    ) -> tuple[str, ...]:
        self.calls.append((documentation, tuple(answers), language.name))
        return ("Dosage for children",)


class World:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.fr = self._language("fr", "French")
        self.bm = self._language("bm", "Bambara")
        project = Project.create(name="P", base_language_id=self.fr)
        protocol = Protocol.create(project_id=project.id, name="Pr")
        theme = Theme.create(protocol_id=protocol.id, name="Malaria")
        self.store.projects.rows[project.id] = project
        self.store.protocols.rows[protocol.id] = protocol
        self.store.themes.rows[theme.id] = theme
        self.theme_id = theme.id
        self.extractor, self.analyzer = FakeExtractor(), FakeAnalyzer()
        self.handler = AnalyzeThemeCompletenessHandler(
            self.store.themes,
            BaseLanguageResolver(self.store.themes, self.store.protocols, self.store.projects),
            self.store.languages,
            self.store.documentation,
            self.store.qasets,
            self.extractor,
            self.analyzer,
        )

    def _language(self, code: str, name: str) -> UUID:
        language = Language.register(LanguageCode(code), name)
        self.store.languages.rows[language.id] = language
        return language.id

    def document(self, filename: str, mime: str = "application/pdf") -> None:
        documentation = Documentation.create(
            theme_id=self.theme_id,
            filename=filename,
            mime_type=mime,
            size_bytes=1,
            checksum_sha256="a" * 64,
            storage_uri=f"memory://documentation/{filename}",
            at=NOW,
        )
        self.store.documentation.rows[documentation.id] = documentation

    def qaset(self, base_answer: str | None, bm_answer: str | None = None) -> None:
        """A QA set answered in French (the base) and/or Bambara."""
        answers = [
            (lang, text) for lang, text in ((self.fr, base_answer), (self.bm, bm_answer)) if text
        ]
        (first_language, first_text), *others = answers
        qaset = QASet.create(
            theme_id=self.theme_id, language_id=first_language, answer_text=first_text
        )
        for language, text in others:
            qaset.add_language(language, text)
        self.store.qasets.rows[qaset.id] = qaset

    async def analyze(self, theme_id: UUID | None = None) -> tuple[str, ...]:
        result = await self.handler(AnalyzeThemeCompletenessQuery(theme_id or self.theme_id))
        return result.uncovered_notions


@pytest.fixture
def world() -> World:
    return World()


async def test_sends_only_base_language_answers_and_the_base_language(world: World) -> None:
    world.document("guide.pdf")
    world.document("notes.docx")
    world.qaset("Buvez de l'eau.", bm_answer="Ji min.")
    world.qaset(None, bm_answer="Only in Bambara")
    world.qaset("Dormez sous une moustiquaire.")

    notions = await world.analyze()

    assert notions == ("Dosage for children",)
    [(documentation, answers, language)] = world.analyzer.calls
    assert language == "French"
    assert sorted(answers) == ["Buvez de l'eau.", "Dormez sous une moustiquaire."]
    assert "text of guide.pdf" in documentation and "text of notes.docx" in documentation
    assert "guide.pdf" in documentation  # each document is introduced by its file name


async def test_unextractable_documents_are_ignored(world: World) -> None:
    world.document("video.mp4", "video/mp4")
    world.document("guide.pdf")
    await world.analyze()
    [(documentation, _, _)] = world.analyzer.calls
    assert "video.mp4" not in documentation


@pytest.mark.parametrize(
    "documents", [[], [("video.mp4", "video/mp4"), ("photo.png", "image/png")]]
)
async def test_no_extractable_documentation_is_a_conflict(
    world: World, documents: list[tuple[str, str]]
) -> None:
    for filename, mime in documents:
        world.document(filename, mime)
    with pytest.raises(NoDocumentationError):
        await world.analyze()
    assert world.analyzer.calls == []


async def test_blank_extractions_count_as_no_documentation(world: World) -> None:
    world.document("empty.pdf")
    world.extractor.texts["empty.pdf"] = "   "
    with pytest.raises(NoDocumentationError):
        await world.analyze()


async def test_unknown_theme(world: World) -> None:
    with pytest.raises(ThemeNotFoundError):
        await world.analyze(uuid4())


async def test_nothing_is_written(world: World) -> None:
    world.document("guide.pdf")
    world.qaset("Buvez.")
    await world.analyze()
    assert world.store.events == []
