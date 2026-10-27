from __future__ import annotations

from uuid import uuid4

import pytest

from qa_authoring.application.author_qa_pairs.command import (
    AuthoredPairsResult,
    AuthorQAPairsCommand,
    QAPair,
)
from qa_authoring.application.qaset_errors import InvalidQAPairsError
from qa_authoring.application.theme_errors import ThemeNotFoundError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from tests.fakes import in_memory_container


class World:
    """A theme whose project's base language is Bambara (French is registered too)."""

    def __init__(self) -> None:
        self.container, self.store = in_memory_container()
        self.fr = Language.register(LanguageCode("fr"), "French")
        self.bm = Language.register(LanguageCode("bm"), "Bambara")
        for language in (self.fr, self.bm):
            self.store.languages.rows[language.id] = language
        project = Project.create(name="Muso", base_language_id=self.bm.id)
        protocol = Protocol.create(project_id=project.id, name="Malaria")
        self.theme = Theme.create(protocol_id=protocol.id, name="Fever")
        self.store.projects.rows[project.id] = project
        self.store.protocols.rows[protocol.id] = protocol
        self.store.themes.rows[self.theme.id] = self.theme

    async def author(self, *pairs: tuple[str, str]) -> AuthoredPairsResult:
        command = AuthorQAPairsCommand(self.theme.id, tuple(QAPair(q, a) for q, a in pairs))
        return await self.container.run(self.container.build_author_qa_pairs, command)

    def qasets(self) -> dict[str, list[str]]:
        """Each QA set of the theme as base answer text -> its base variant texts, in order."""
        result = {}
        for qaset in self.store.qasets.rows.values():
            if qaset.theme_id != self.theme.id:
                continue
            presence = qaset.presence(self.bm.id)
            result[presence.answer.text] = [v.text for v in presence.variants]
        return result


@pytest.fixture
def world() -> World:
    return World()


async def test_pairs_sharing_an_answer_form_one_qaset_in_the_base_language(world: World) -> None:
    result = await world.author(("Q1", "A"), ("Q2", "B"), ("Q3", " A "), ("Q4", "A"), ("Q5", "B"))

    assert result == AuthoredPairsResult(
        qasets_created=2, qasets_updated=0, variants_added=5, skipped_rows=()
    )
    assert world.qasets() == {"A": ["Q1", "Q3", "Q4"], "B": ["Q2", "Q5"]}
    for qaset in world.store.qasets.rows.values():
        assert [a.language_id for a in qaset.answers] == [world.bm.id]


async def test_questions_are_deduplicated_within_the_batch(world: World) -> None:
    result = await world.author(("Q1", "A"), (" Q1 ", "A"), ("Q2", "A"), ("q1", "A"))

    assert (result.variants_added, result.skipped_rows) == (3, (1,))
    assert world.qasets() == {"A": ["Q1", "Q2", "q1"]}


async def test_an_existing_answer_is_merged_into_and_its_questions_are_not_repeated(
    world: World,
) -> None:
    existing = QASet.create(theme_id=world.theme.id, language_id=world.bm.id, answer_text="A")
    existing.add_variant(world.bm.id, "Q1")
    await world.store.qasets.add(existing)

    result = await world.author(("Q1", "A"), ("Q2", " A"), ("Q3", "C"))

    assert result == AuthoredPairsResult(
        qasets_created=1, qasets_updated=1, variants_added=2, skipped_rows=(0,)
    )
    assert world.qasets() == {"A": ["Q1", "Q2"], "C": ["Q3"]}
    assert len(world.store.qasets.rows) == 2


async def test_an_existing_qaset_left_unchanged_is_not_counted_as_updated(world: World) -> None:
    existing = QASet.create(theme_id=world.theme.id, language_id=world.bm.id, answer_text="A")
    existing.add_variant(world.bm.id, "Q1")
    await world.store.qasets.add(existing)

    result = await world.author(("Q1", "A"))

    assert result == AuthoredPairsResult(0, 0, 0, (0,))
    assert "save" not in world.store.qasets.events


async def test_only_the_base_language_answer_and_this_theme_are_matched(world: World) -> None:
    french_only = QASet.create(theme_id=world.theme.id, language_id=world.fr.id, answer_text="A")
    elsewhere = QASet.create(theme_id=uuid4(), language_id=world.bm.id, answer_text="A")
    await world.store.qasets.add(french_only)
    await world.store.qasets.add(elsewhere)

    result = await world.author(("Q1", "A"))

    assert (result.qasets_created, result.qasets_updated) == (1, 0)
    assert world.store.qasets.rows[french_only.id].variants == ()
    assert world.store.qasets.rows[elsewhere.id].variants == ()


async def test_empty_questions_or_answers_reject_the_whole_batch(world: World) -> None:
    with pytest.raises(InvalidQAPairsError) as raised:
        await world.author(("Q1", "A"), ("  ", "A"), ("Q3", ""), ("Q4", "B"))

    assert raised.value.rows == (1, 2)
    assert world.store.qasets.rows == {}


async def test_an_unknown_theme(world: World) -> None:
    command = AuthorQAPairsCommand(uuid4(), (QAPair("Q", "A"),))
    with pytest.raises(ThemeNotFoundError):
        await world.container.run(world.container.build_author_qa_pairs, command)
