from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.audio_errors import AudioNotFoundError
from qa_authoring.application.get_audio_validation.command import GetAudioValidationQuery
from qa_authoring.application.get_clinical_validation.command import GetClinicalValidationQuery
from qa_authoring.application.get_qaset.command import GetQASetQuery
from qa_authoring.application.get_translation_validation.command import (
    GetTranslationValidationQuery,
)
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.application.record_audio_decision.command import RecordAudioDecisionCommand
from qa_authoring.application.record_clinical_decision.command import (
    RecordClinicalDecisionCommand,
)
from qa_authoring.application.record_translation_decision.command import (
    RecordTranslationDecisionCommand,
)
from qa_authoring.application.validation_errors import (
    NoBaseLanguagePresenceError,
    NotATranslationError,
)
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    QASet,
    QuestionVariantNotFoundError,
)
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.validation import InvalidDecisionError
from tests.fakes import NOW, in_memory_container, seed_user
from tests.qa_authoring.domain.model.test_audio import audio

if TYPE_CHECKING:
    from config.container import Container
    from tests.fakes import InMemoryStore

FR, BM = uuid4(), uuid4()  # FR is the project's base language


class World:
    def __init__(self) -> None:
        self.container, self.store = in_memory_container()
        project = Project.create(name="P", base_language_id=FR)
        protocol = Protocol.create(project_id=project.id, name="Pr")
        theme = Theme.create(protocol_id=protocol.id, name="T")
        self.store.projects.rows[project.id] = project
        self.store.protocols.rows[protocol.id] = protocol
        self.store.themes.rows[theme.id] = theme
        self.theme_id = theme.id
        self.alice = seed_user(self.store, "alice@example.org", *Permission).id
        self.bob = seed_user(self.store, "bob@example.org", *Permission).id

    def qaset(self, *languages: UUID) -> QASet:
        qaset = QASet.create(theme_id=self.theme_id, language_id=languages[0], answer_text="a")
        for language in languages[1:]:
            qaset.add_language(language, "b")
        for language in languages:
            qaset.add_variant(language, "q")
        self.store.qasets.rows[qaset.id] = qaset
        return qaset


@pytest.fixture
def world() -> World:
    return World()


def _answer(qaset: QASet, language: UUID) -> UUID:
    return qaset.presence(language).answer.id


def _variant(qaset: QASet, language: UUID) -> UUID:
    return qaset.presence(language).variants[0].id


async def _clinical(
    c: Container, qaset_id: UUID, decision: str, actor: UUID, note: str | None = None
) -> object:
    return await c.run(
        c.build_record_clinical_decision,
        RecordClinicalDecisionCommand(qaset_id, decision, actor_user_id=actor, note=note),
    )


# --- clinical ---


async def test_clinical_decisions_record_the_actor_and_history(world: World) -> None:
    c = world.container
    qaset = world.qaset(FR, BM)

    first, created = await c.run(
        c.build_record_clinical_decision,
        RecordClinicalDecisionCommand(qaset.id, "validated", actor_user_id=world.alice, note="ok"),
    )
    second, created_again = await c.run(
        c.build_record_clinical_decision,
        RecordClinicalDecisionCommand(qaset.id, "rejected", actor_user_id=world.bob),
    )

    assert (created, created_again) == (True, False)
    assert (first.kind, first.state) == ("clinical", "validated")
    assert second.state == "rejected"
    assert [
        (e.from_state, e.to_state, e.actor_email, e.note, e.occurred_at) for e in second.history
    ] == [
        (None, "validated", "alice@example.org", "ok", NOW),
        ("validated", "rejected", "bob@example.org", None, NOW),
    ]
    history = await c.run(c.build_get_clinical_validation, GetClinicalValidationQuery(qaset.id))
    assert history == second


async def test_clinical_needs_an_answer_in_the_base_language(world: World) -> None:
    c = world.container
    qaset = world.qaset(BM)
    with pytest.raises(NoBaseLanguagePresenceError):
        await _clinical(c, qaset.id, "validated", world.alice)
    assert world.store.validations.rows == {}


async def test_unknown_qaset_and_decision(world: World) -> None:
    c = world.container
    with pytest.raises(QASetNotFoundError):
        await _clinical(c, uuid4(), "validated", world.alice)
    with pytest.raises(QASetNotFoundError):
        await c.run(c.build_get_clinical_validation, GetClinicalValidationQuery(uuid4()))
    with pytest.raises(InvalidDecisionError):
        await _clinical(c, world.qaset(FR).id, "approved", world.alice)


async def test_pending_until_the_first_decision(world: World) -> None:
    c = world.container
    qaset = world.qaset(FR)
    pending = await c.run(c.build_get_clinical_validation, GetClinicalValidationQuery(qaset.id))
    assert (pending.kind, pending.state, pending.history) == ("clinical", "pending", ())


# --- translation ---


async def test_translation_of_answers_and_variants(world: World) -> None:
    c = world.container
    qaset = world.qaset(FR, BM)

    answer, _ = await c.run(
        c.build_record_translation_decision,
        RecordTranslationDecisionCommand(
            "validated", actor_user_id=world.alice, answer_id=_answer(qaset, BM)
        ),
    )
    variant, _ = await c.run(
        c.build_record_translation_decision,
        RecordTranslationDecisionCommand(
            "rejected", actor_user_id=world.bob, variant_id=_variant(qaset, BM), note="Wrong"
        ),
    )

    assert (answer.kind, answer.state, variant.state) == ("translation", "validated", "rejected")
    got = await c.run(
        c.build_get_translation_validation,
        GetTranslationValidationQuery(variant_id=_variant(qaset, BM)),
    )
    assert [(e.to_state, e.actor_email, e.note) for e in got.history] == [
        ("rejected", "bob@example.org", "Wrong")
    ]


async def test_base_language_items_are_not_translations(world: World) -> None:
    c = world.container
    qaset = world.qaset(FR, BM)
    for command in (
        RecordTranslationDecisionCommand(
            "validated", actor_user_id=world.alice, answer_id=_answer(qaset, FR)
        ),
        RecordTranslationDecisionCommand(
            "validated", actor_user_id=world.alice, variant_id=_variant(qaset, FR)
        ),
    ):
        with pytest.raises(NotATranslationError):
            await c.run(c.build_record_translation_decision, command)
    assert world.store.validations.rows == {}


async def test_unknown_translation_items(world: World) -> None:
    c = world.container
    with pytest.raises(AnswerNotFoundError):
        await c.run(
            c.build_record_translation_decision,
            RecordTranslationDecisionCommand(
                "validated", actor_user_id=world.alice, answer_id=uuid4()
            ),
        )
    with pytest.raises(QuestionVariantNotFoundError):
        await c.run(
            c.build_get_translation_validation, GetTranslationValidationQuery(variant_id=uuid4())
        )


# --- audio ---


async def test_audio_decisions(world: World) -> None:
    c = world.container
    qaset = world.qaset(FR)
    reference = audio()
    qaset.set_variant_audio(_variant(qaset, FR), reference)

    result, created = await c.run(
        c.build_record_audio_decision,
        RecordAudioDecisionCommand(
            reference.id, "rejected", actor_user_id=world.alice, note="Hiss"
        ),
    )

    assert (created, result.kind, result.state) == (True, "audio", "rejected")
    got = await c.run(c.build_get_audio_validation, GetAudioValidationQuery(reference.id))
    assert got == result
    with pytest.raises(AudioNotFoundError):
        await c.run(
            c.build_record_audio_decision,
            RecordAudioDecisionCommand(uuid4(), "validated", actor_user_id=world.alice),
        )


# --- read integration ---


async def test_qaset_read_shows_current_states_only(world: World) -> None:
    c = world.container
    qaset = world.qaset(FR, BM)
    reference = audio()
    qaset.set_answer_audio(_answer(qaset, BM), reference)
    await _clinical(c, qaset.id, "validated", world.alice)
    await c.run(
        c.build_record_translation_decision,
        RecordTranslationDecisionCommand(
            "rejected", actor_user_id=world.alice, variant_id=_variant(qaset, BM)
        ),
    )
    await c.run(
        c.build_record_audio_decision,
        RecordAudioDecisionCommand(reference.id, "validated", actor_user_id=world.bob),
    )

    result = await c.run(c.build_get_qaset, GetQASetQuery(qaset.id))

    assert result.clinical_validation == "validated"
    by_language = {p.language_id: p for p in result.languages}
    fr, bm = by_language[FR], by_language[BM]
    assert (fr.answer.translation_validation, fr.variants[0].translation_validation) == (None, None)
    assert bm.answer.translation_validation is None
    assert bm.variants[0].translation_validation == "rejected"
    assert bm.answer.audio is not None
    assert bm.answer.audio.audio_validation == "validated"


async def test_store_is_untouched_by_refused_decisions(world: World) -> None:
    store: InMemoryStore = world.store
    qaset = world.qaset(BM)
    with pytest.raises(NoBaseLanguagePresenceError):
        await _clinical(world.container, qaset.id, "validated", world.alice)
    assert store.validations.rows == {}
