from __future__ import annotations

from uuid import uuid4

import pytest

from qa_authoring.application.generate_variants.command import GenerateVariantsQuery
from qa_authoring.application.generate_variants.handler import GenerateVariantsHandler
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.qaset import AnswerNotFoundError, QASet
from qa_authoring.domain.value_objects.language_code import LanguageCode
from tests.fakes import FakeVariantGenerator, InMemoryStore


class World:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.fr = Language.register(LanguageCode("fr"), "French")
        self.bm = Language.register(LanguageCode("bm"), "Bambara")
        for language in (self.fr, self.bm):
            self.store.languages.rows[language.id] = language
        qaset = QASet.create(theme_id=uuid4(), language_id=self.fr.id, answer_text="Buvez.")
        qaset.add_language(self.bm.id, "Ji min.")
        qaset.add_variant(self.fr.id, "Que boire ?")
        self.store.qasets.rows[qaset.id] = qaset
        self.qaset = qaset
        self.generator = FakeVariantGenerator()
        self.handler = GenerateVariantsHandler(
            self.store.qasets, self.store.languages, self.generator
        )


@pytest.fixture
def world() -> World:
    return World()


async def test_generates_in_the_answers_language(world: World) -> None:
    answer = world.qaset.presence(world.bm.id).answer

    result = await world.handler(GenerateVariantsQuery(world.qaset.id, answer.id, "fever"))

    assert result.candidates == ("Ji min. (Bambara) #1", "Ji min. (Bambara) #2")
    assert world.generator.calls == [("Ji min.", (), "fever", "bm")]


async def test_is_seeded_with_the_answer_existing_questions(world: World) -> None:
    world.qaset.add_variant(world.fr.id, "Et pour un enfant ?")
    world.qaset.add_variant(world.bm.id, "Mun bɛ min ?")
    world.store.qasets.rows[world.qaset.id] = world.qaset
    answer = world.qaset.presence(world.fr.id).answer

    await world.handler(GenerateVariantsQuery(world.qaset.id, answer.id, ""))

    [(_, existing, _, language)] = world.generator.calls
    assert language == "fr"
    assert sorted(existing) == ["Et pour un enfant ?", "Que boire ?"]


async def test_candidates_repeating_an_existing_question_are_dropped(world: World) -> None:
    answer = world.qaset.presence(world.fr.id).answer
    world.generator.replies = ("  Que boire ?  ", "Que faut-il boire ?", "que boire ?")

    result = await world.handler(GenerateVariantsQuery(world.qaset.id, answer.id, ""))

    assert result.candidates == ("Que faut-il boire ?", "que boire ?")


async def test_unknown_subjects(world: World) -> None:
    with pytest.raises(QASetNotFoundError):
        await world.handler(GenerateVariantsQuery(uuid4(), world.qaset.answers[0].id, ""))
    with pytest.raises(AnswerNotFoundError):
        await world.handler(GenerateVariantsQuery(world.qaset.id, uuid4(), ""))
    assert world.generator.calls == []


async def test_nothing_is_written(world: World) -> None:
    before = (len(world.qaset.variants), list(world.store.events))
    await world.handler(GenerateVariantsQuery(world.qaset.id, world.qaset.answers[0].id, ""))
    stored = world.store.qasets.rows[world.qaset.id]
    assert (len(stored.variants), world.store.events) == before
    assert "save" not in world.store.events
