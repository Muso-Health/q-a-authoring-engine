from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.add_question_variant.command import AddQuestionVariantCommand
from qa_authoring.application.attach_intent.command import AttachIntentCommand
from qa_authoring.application.delete_question_variant.command import (
    DeleteQuestionVariantCommand,
)
from qa_authoring.application.record_clinical_decision.command import (
    RecordClinicalDecisionCommand,
)
from qa_authoring.application.record_translation_decision.command import (
    RecordTranslationDecisionCommand,
)
from qa_authoring.application.remove_language_presence.command import (
    RemoveLanguagePresenceCommand,
)
from qa_authoring.application.set_answer_audio.command import SetAnswerAudioCommand
from qa_authoring.application.update_answer.command import UpdateAnswerCommand
from qa_authoring.application.update_question_variant.command import (
    UpdateQuestionVariantCommand,
)
from qa_authoring.domain.model.intent import Intent
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.validation import ValidationState, ValidationSubject
from tests.fakes import in_memory_container, seed_user

if TYPE_CHECKING:
    from config.container import Container
    from tests.fakes import InMemoryStore

FR, BM = uuid4(), uuid4()  # FR is the project's base language
PENDING, VALIDATED, REJECTED = (
    ValidationState.PENDING,
    ValidationState.VALIDATED,
    ValidationState.REJECTED,
)


class World:
    """A French-based project with a QA set in French and Bambara, one variant each, its
    clinical validation and both Bambara items' translation validations decided."""

    def __init__(self) -> None:
        self.container, self.store = in_memory_container()
        project = Project.create(name="P", base_language_id=FR)
        protocol = Protocol.create(project_id=project.id, name="Pr")
        theme = Theme.create(protocol_id=protocol.id, name="T")
        self.store.projects.rows[project.id] = project
        self.store.protocols.rows[protocol.id] = protocol
        self.store.themes.rows[theme.id] = theme
        self.reviewer = seed_user(self.store, "reviewer@example.org", *Permission).id
        self.editor = seed_user(self.store, "editor@example.org", Permission.AUTHOR_QASETS).id
        qaset = QASet.create(theme_id=theme.id, language_id=FR, answer_text="fr answer")
        qaset.add_language(BM, "bm answer")
        qaset.add_variant(FR, "fr question")
        qaset.add_variant(BM, "bm question")
        self.store.qasets.rows[qaset.id] = qaset
        self.qaset_id = qaset.id

    @property
    def qaset(self) -> QASet:
        return self.store.qasets.rows[self.qaset_id]

    def answer(self, language: UUID) -> UUID:
        return self.qaset.presence(language).answer.id

    def variant(self, language: UUID) -> UUID:
        return self.qaset.presence(language).variants[0].id

    async def decide_all(self) -> None:
        c = self.container
        await c.run(
            c.build_record_clinical_decision,
            RecordClinicalDecisionCommand(self.qaset_id, "validated", actor_user_id=self.reviewer),
        )
        for command in (
            RecordTranslationDecisionCommand(
                "rejected", actor_user_id=self.reviewer, answer_id=self.answer(BM)
            ),
            RecordTranslationDecisionCommand(
                "rejected", actor_user_id=self.reviewer, variant_id=self.variant(BM)
            ),
        ):
            await c.run(c.build_record_translation_decision, command)

    def states(
        self,
    ) -> tuple[ValidationState | None, ValidationState | None, ValidationState | None]:
        rows = self.store.validations.rows

        def state(subject: ValidationSubject) -> ValidationState | None:
            return rows[subject].current_state if subject in rows else None

        return (
            state(ValidationSubject.for_qaset(self.qaset_id)),
            state(ValidationSubject.for_answer(self.answer(BM))),
            state(ValidationSubject.for_variant(self.variant(BM))),
        )

    async def run(self, build_name: str, command: object) -> object:
        return await self.container.run(getattr(self.container, build_name), command)


@pytest.fixture
async def world() -> World:
    world = World()
    await world.decide_all()
    assert world.states() == (VALIDATED, REJECTED, REJECTED)
    return world


async def test_editing_the_base_answer_resets_clinical_only(world: World) -> None:
    await world.run(
        "build_update_answer",
        UpdateAnswerCommand(world.qaset_id, FR, "new fr answer", actor_user_id=world.editor),
    )

    assert world.states() == (PENDING, REJECTED, REJECTED)
    clinical = world.store.validations.rows[ValidationSubject.for_qaset(world.qaset_id)]
    reset = clinical.events[-1]
    assert (reset.from_state, reset.to_state, reset.actor_user_id, reset.note) == (
        VALIDATED,
        PENDING,
        world.editor,
        "content changed",
    )


async def test_base_variant_changes_reset_clinical(world: World) -> None:
    store: InMemoryStore = world.store
    clinical = ValidationSubject.for_qaset(world.qaset_id)
    container: Container = world.container

    async def revalidate() -> None:
        await container.run(
            container.build_record_clinical_decision,
            RecordClinicalDecisionCommand(
                world.qaset_id, "validated", actor_user_id=world.reviewer
            ),
        )

    await world.run(
        "build_add_question_variant",
        AddQuestionVariantCommand(world.qaset_id, FR, "another", actor_user_id=world.editor),
    )
    assert store.validations.rows[clinical].current_state is PENDING

    await revalidate()
    await world.run(
        "build_update_question_variant",
        UpdateQuestionVariantCommand(
            world.qaset_id, world.variant(FR), "edited", actor_user_id=world.editor
        ),
    )
    assert store.validations.rows[clinical].current_state is PENDING

    await revalidate()
    await world.run(
        "build_delete_question_variant",
        DeleteQuestionVariantCommand(world.qaset_id, world.variant(FR), actor_user_id=world.editor),
    )
    assert world.states() == (PENDING, REJECTED, REJECTED)


async def test_removing_the_base_presence_resets_clinical(world: World) -> None:
    await world.run(
        "build_remove_language_presence",
        RemoveLanguagePresenceCommand(world.qaset_id, FR, actor_user_id=world.editor),
    )
    clinical = world.store.validations.rows[ValidationSubject.for_qaset(world.qaset_id)]
    assert clinical.current_state is PENDING


async def test_editing_a_translated_item_resets_its_translation_only(world: World) -> None:
    await world.run(
        "build_update_answer",
        UpdateAnswerCommand(world.qaset_id, BM, "new bm answer", actor_user_id=world.editor),
    )
    assert world.states() == (VALIDATED, PENDING, REJECTED)

    await world.run(
        "build_update_question_variant",
        UpdateQuestionVariantCommand(
            world.qaset_id, world.variant(BM), "new bm question", actor_user_id=world.editor
        ),
    )
    assert world.states() == (VALIDATED, PENDING, PENDING)


async def test_non_base_structure_changes_do_not_reset_clinical(world: World) -> None:
    await world.run(
        "build_add_question_variant",
        AddQuestionVariantCommand(world.qaset_id, BM, "another bm", actor_user_id=world.editor),
    )
    await world.run(
        "build_delete_question_variant",
        DeleteQuestionVariantCommand(world.qaset_id, world.variant(BM), actor_user_id=world.editor),
    )
    clinical = world.store.validations.rows[ValidationSubject.for_qaset(world.qaset_id)]
    assert clinical.current_state is VALIDATED


async def test_a_no_op_edit_resets_nothing(world: World) -> None:
    before = {s: len(v.events) for s, v in world.store.validations.rows.items()}
    await world.run(
        "build_update_answer",
        UpdateAnswerCommand(world.qaset_id, FR, "  fr answer  ", actor_user_id=world.editor),
    )
    await world.run(
        "build_update_question_variant",
        UpdateQuestionVariantCommand(
            world.qaset_id, world.variant(BM), "bm question", actor_user_id=world.editor
        ),
    )
    assert world.states() == (VALIDATED, REJECTED, REJECTED)
    assert {s: len(v.events) for s, v in world.store.validations.rows.items()} == before


async def test_an_already_pending_validation_gets_no_second_reset(world: World) -> None:
    for text in ("one", "two"):
        await world.run(
            "build_update_answer",
            UpdateAnswerCommand(world.qaset_id, FR, text, actor_user_id=world.editor),
        )
    clinical = world.store.validations.rows[ValidationSubject.for_qaset(world.qaset_id)]
    assert [e.to_state for e in clinical.events] == [VALIDATED, PENDING]


async def test_tags_and_audio_do_not_reset_text_validations(world: World) -> None:
    intent = Intent.register("Dosage")
    world.store.intents.rows[intent.id] = intent
    await world.run(
        "build_attach_intent",
        AttachIntentCommand(world.qaset_id, world.variant(FR), intent.id),
    )
    await world.run(
        "build_set_answer_audio",
        SetAnswerAudioCommand(world.qaset_id, world.answer(FR), b"sound", client_mime=None),
    )
    assert world.states() == (VALIDATED, REJECTED, REJECTED)


async def test_edits_without_any_validation_need_no_catalog_lookup() -> None:
    # A variant edit only: editing an answer resolves the base language anyway, to keep each
    # base-language answer once per theme.
    world = World()  # nothing decided
    world.store.themes.rows.clear()  # resolving the base language would now fail
    await world.run(
        "build_update_question_variant",
        UpdateQuestionVariantCommand(
            world.qaset_id, world.variant(FR), "edited", actor_user_id=world.editor
        ),
    )
    assert world.store.validations.rows == {}
