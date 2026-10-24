from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.get_qaset.command import GetQASetQuery
from qa_authoring.application.ports.translator import (
    TranslationEngineError,
    UnsupportedLanguageForEngineError,
)
from qa_authoring.application.qaset_errors import QASetNotFoundError, UnknownLanguageError
from qa_authoring.application.record_clinical_decision.command import (
    RecordClinicalDecisionCommand,
)
from qa_authoring.application.translate_answer.command import TranslateAnswerCommand
from qa_authoring.application.translate_variant.command import TranslateVariantCommand
from qa_authoring.application.translation_engines import UnknownEngineError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    PromptTemplate,
    PromptTemplateKey,
)
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    LanguageAlreadyPresentError,
    LanguagePresenceRequiredError,
    QASet,
    QuestionVariantNotFoundError,
    SameLanguageError,
)
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.validation import ValidationState, ValidationSubject
from qa_authoring.domain.value_objects.language_code import LanguageCode
from tests.fakes import NOW, in_memory_container, seed_user

if TYPE_CHECKING:
    from qa_authoring.application.translation_response import (
        TranslatedAnswerResult,
        TranslatedVariantResult,
    )


class World:
    """A French-based project; the QA set has a French answer and question."""

    def __init__(self) -> None:
        self.container, self.store = in_memory_container()
        self.fr, self.bm, self.en = (
            self._language("fr", "French"),
            self._language("bm", "Bambara"),
            self._language("en", "English"),
        )
        project = Project.create(name="P", base_language_id=self.fr)
        protocol = Protocol.create(project_id=project.id, name="Pr")
        theme = Theme.create(protocol_id=protocol.id, name="T")
        self.store.projects.rows[project.id] = project
        self.store.protocols.rows[protocol.id] = protocol
        self.store.themes.rows[theme.id] = theme
        for key in PromptTemplateKey:
            self.store.prompt_templates.rows[key] = PromptTemplate.create(
                key, DEFAULT_TEMPLATES[key], updated_by=None, at=NOW
            )
        self.author = seed_user(self.store, "author@example.org", *Permission).id
        qaset = QASet.create(theme_id=theme.id, language_id=self.fr, answer_text="Buvez de l'eau.")
        qaset.add_variant(self.fr, "Que faire en cas de fièvre ?")
        self.store.qasets.rows[qaset.id] = qaset
        self.qaset_id = qaset.id

    def _language(self, code: str, name: str) -> UUID:
        language = Language.register(LanguageCode(code), name)
        self.store.languages.rows[language.id] = language
        return language.id

    @property
    def qaset(self) -> QASet:
        return self.store.qasets.rows[self.qaset_id]

    def answer(self, language: UUID) -> UUID:
        return self.qaset.presence(language).answer.id

    def variant(self, language: UUID) -> UUID:
        return self.qaset.presence(language).variants[0].id

    async def translate_answer(
        self, target: UUID, engine: str = "google", **overrides: UUID
    ) -> TranslatedAnswerResult:
        command = TranslateAnswerCommand(
            qaset_id=overrides.get("qaset_id", self.qaset_id),
            answer_id=overrides.get("answer_id", self.answer(self.fr)),
            target_language_id=target,
            engine=engine,
            actor_user_id=self.author,
        )
        return await self.container.run(self.container.build_translate_answer, command)

    async def translate_variant(
        self, source: UUID, target: UUID, engine: str = "google", **overrides: UUID
    ) -> TranslatedVariantResult:
        command = TranslateVariantCommand(
            qaset_id=overrides.get("qaset_id", self.qaset_id),
            variant_id=overrides.get("variant_id", self.variant(source)),
            target_language_id=target,
            engine=engine,
            actor_user_id=self.author,
        )
        return await self.container.run(self.container.build_translate_variant, command)


@pytest.fixture
def world() -> World:
    return World()


async def test_answer_translation_creates_the_presence_and_a_symmetric_link(world: World) -> None:
    result = await world.translate_answer(world.bm)

    bm = world.qaset.presence(world.bm)
    source = world.answer(world.fr)
    assert bm.answer.text == "bm: Buvez de l'eau."
    assert [t.other_id for t in world.qaset.answer_translations(source)] == [bm.answer.id]
    assert [t.other_id for t in world.qaset.answer_translations(bm.answer.id)] == [source]
    assert result.presence.language_id == world.bm
    assert result.presence.answer.id == bm.answer.id
    assert set(result.link.item_ids) == {source, bm.answer.id}
    assert world.store.google_translator.calls == [("Buvez de l'eau.", "fr", "bm")]


async def test_the_llm_engine_renders_the_translation_template_with_language_names(
    world: World,
) -> None:
    await world.translate_answer(world.bm, engine="llm")

    [prompt] = world.store.llm.prompts
    assert "from French into Bambara" in prompt
    assert "Buvez de l'eau." in prompt
    assert "{" not in prompt
    assert world.qaset.presence(world.bm).answer.text == "Traduction du modèle"
    assert world.store.google_translator.calls == []


async def test_variant_translation_needs_the_target_presence(world: World) -> None:
    with pytest.raises(LanguagePresenceRequiredError):
        await world.translate_variant(world.fr, world.bm)
    assert world.store.google_translator.calls == []

    await world.translate_answer(world.bm)
    result = await world.translate_variant(world.fr, world.bm)

    [bm_variant] = world.qaset.presence(world.bm).variants
    source = world.variant(world.fr)
    assert bm_variant.text == "bm: Que faire en cas de fièvre ?"
    assert [t.other_id for t in world.qaset.variant_translations(bm_variant.id)] == [source]
    assert result.variant.id == bm_variant.id
    assert set(result.link.item_ids) == {source, bm_variant.id}


async def test_a_present_target_is_a_conflict_before_any_engine_call(world: World) -> None:
    await world.translate_answer(world.bm)
    calls = list(world.store.google_translator.calls)
    with pytest.raises(LanguageAlreadyPresentError):
        await world.translate_answer(world.bm)
    assert world.store.google_translator.calls == calls


async def test_invalid_requests_are_refused_before_any_engine_call(world: World) -> None:
    with pytest.raises(SameLanguageError):
        await world.translate_answer(world.fr)
    with pytest.raises(UnknownLanguageError):
        await world.translate_answer(uuid4())
    with pytest.raises(UnknownEngineError):
        await world.translate_answer(world.bm, engine="babelfish")
    with pytest.raises(AnswerNotFoundError):
        await world.translate_answer(world.bm, answer_id=uuid4())
    with pytest.raises(QASetNotFoundError):
        await world.translate_answer(world.bm, qaset_id=uuid4())
    with pytest.raises(QuestionVariantNotFoundError):
        await world.translate_variant(world.fr, world.bm, variant_id=uuid4())
    assert world.store.google_translator.calls == []
    assert world.store.llm.prompts == []


@pytest.mark.parametrize("engine", ["google", "llm"])
async def test_an_engine_failure_persists_nothing(world: World, engine: str) -> None:
    world.store.google_translator.failing = True
    world.store.llm.failing = True

    with pytest.raises(TranslationEngineError):
        await world.translate_answer(world.bm, engine=engine)

    assert [p.language_id for p in world.qaset.presences()] == [world.fr]
    assert world.qaset.answer_links == ()
    assert world.store.events[-1] == "rollback"


async def test_an_unsupported_language_is_a_clean_error(world: World) -> None:
    world.store.google_translator.unsupported = {"bm"}
    with pytest.raises(UnsupportedLanguageForEngineError) as raised:
        await world.translate_answer(world.bm)
    assert (raised.value.engine, raised.value.language_code) == ("google", "bm")
    assert [p.language_id for p in world.qaset.presences()] == [world.fr]


async def test_the_new_item_starts_unvalidated(world: World) -> None:
    await world.translate_answer(world.bm)
    await world.translate_variant(world.fr, world.bm)

    result = await world.container.run(
        world.container.build_get_qaset, GetQASetQuery(world.qaset_id)
    )

    bm = next(p for p in result.languages if p.language_id == world.bm)
    assert bm.answer.translation_validation is None
    assert bm.variants[0].translation_validation is None
    assert world.store.validations.rows == {}


async def test_translating_into_the_base_language_resets_clinical(world: World) -> None:
    await world.translate_answer(world.bm)
    await world.translate_variant(world.fr, world.bm)
    c = world.container
    await c.run(
        c.build_record_clinical_decision,
        RecordClinicalDecisionCommand(world.qaset_id, "validated", actor_user_id=world.author),
    )

    await world.translate_variant(world.bm, world.fr)

    clinical = world.store.validations.rows[ValidationSubject.for_qaset(world.qaset_id)]
    assert clinical.current_state is ValidationState.PENDING
    assert clinical.events[-1].actor_user_id == world.author
