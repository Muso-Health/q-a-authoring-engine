from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.user import User
from qa_authoring.domain.model.validation import (
    Validation,
    ValidationState,
    ValidationSubject,
)
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.qa_authoring.domain.model.test_audio import audio

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

T0 = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


class World:
    def __init__(self, qaset: QASet, fr: UUID, bm: UUID, actor: UUID) -> None:
        self.qaset, self.fr, self.bm, self.actor = qaset, fr, bm, actor


async def _world(engine: AsyncEngine) -> World:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="a")
    qaset.add_language(bm.id, "b")
    variant = qaset.add_variant(bm.id, "q")
    qaset.set_variant_audio(variant.id, audio())
    actor = User.create(email="alice@example.org", display_name="Alice")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        for language in (fr, bm):
            await uow.languages.add(language)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
        await uow.users.add(actor)
    return World(qaset, fr.id, bm.id, actor.id)


def _subjects(world: World) -> list[ValidationSubject]:
    bm = world.qaset.presence(world.bm)
    variant_audio = bm.variants[0].audio
    assert variant_audio is not None
    return [
        ValidationSubject.for_qaset(world.qaset.id),
        ValidationSubject.for_answer(bm.answer.id),
        ValidationSubject.for_variant(bm.variants[0].id),
        ValidationSubject.for_audio(variant_audio.id),
    ]


async def _record(engine: AsyncEngine, world: World, subject: ValidationSubject) -> Validation:
    validation = Validation.start(
        subject, ValidationState.VALIDATED, actor_user_id=world.actor, at=T0, note="first"
    )
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.validations.add(validation)
    return validation


async def _count(engine: AsyncEngine, table: str) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text(f"SELECT count(*) FROM {table}")) or 0)


async def test_validations_and_events_round_trip(migrated_engine: AsyncEngine) -> None:
    world = await _world(migrated_engine)
    for subject in _subjects(world):
        await _record(migrated_engine, world, subject)
    clinical = _subjects(world)[0]

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.validations.get_for(clinical)
        assert loaded is not None
        loaded.decide(
            ValidationState.REJECTED, actor_user_id=world.actor, at=T0 + timedelta(hours=1)
        )
        loaded.decide(
            ValidationState.VALIDATED,
            actor_user_id=world.actor,
            at=T0 + timedelta(hours=2),
            note="again",
        )
        await uow.validations.save(loaded)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        reloaded = await uow.validations.get_for(clinical)
        states = await uow.validations.current_states(
            {*_subjects(world), ValidationSubject.for_qaset(uuid4())}
        )

    assert reloaded is not None
    assert reloaded.id == loaded.id
    assert reloaded.current_state is ValidationState.VALIDATED
    assert [
        (e.sequence, e.from_state, e.to_state, e.note, e.occurred_at) for e in reloaded.events
    ] == [
        (1, None, ValidationState.VALIDATED, "first", T0),
        (2, ValidationState.VALIDATED, ValidationState.REJECTED, None, T0 + timedelta(hours=1)),
        (3, ValidationState.REJECTED, ValidationState.VALIDATED, "again", T0 + timedelta(hours=2)),
    ]
    assert states == dict.fromkeys(_subjects(world), ValidationState.VALIDATED)


async def test_one_validation_per_subject(migrated_engine: AsyncEngine) -> None:
    world = await _world(migrated_engine)
    subject = _subjects(world)[1]
    await _record(migrated_engine, world, subject)
    with pytest.raises(IntegrityError, match="uq_validations_answer_id"):
        await _record(migrated_engine, world, subject)


@pytest.mark.parametrize(
    ("kind", "columns"),
    [
        ("clinical", ("answer_id",)),
        ("translation", ("qaset_id",)),
        ("audio", ("variant_id",)),
        ("translation", ("answer_id", "variant_id")),
        ("clinical", ()),
        ("other", ("qaset_id",)),
    ],
)
async def test_subject_check(
    migrated_engine: AsyncEngine, kind: str, columns: tuple[str, ...]
) -> None:
    world = await _world(migrated_engine)
    bm = world.qaset.presence(world.bm)
    ids = {"qaset_id": world.qaset.id, "answer_id": bm.answer.id, "variant_id": bm.variants[0].id}
    values = {column: ids[column] for column in columns}
    names = ", ".join(["id", "kind", "current_state", "updated_at", *values])
    params = ", ".join([":id", ":kind", "'validated'", "now()", *(f":{c}" for c in values)])
    with pytest.raises(IntegrityError, match="ck_validations"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text(f"INSERT INTO validations ({names}) VALUES ({params})"),
                {"id": uuid4(), "kind": kind, **values},
            )


async def test_deleting_subjects_cascades_their_validations(migrated_engine: AsyncEngine) -> None:
    world = await _world(migrated_engine)
    clinical, answer, variant, audio_subject = _subjects(world)
    for subject in (clinical, answer, variant, audio_subject):
        await _record(migrated_engine, world, subject)
    assert await _count(migrated_engine, "validations") == 4

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(world.qaset.id)
        assert loaded is not None
        loaded.remove_variant_audio(loaded.presence(world.bm).variants[0].id)
        await uow.qasets.save(loaded)
    assert await _count(migrated_engine, "validations") == 3

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(world.qaset.id)
        assert loaded is not None
        loaded.remove_variant(loaded.presence(world.bm).variants[0].id)
        await uow.qasets.save(loaded)
    assert await _count(migrated_engine, "validations") == 2

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(world.qaset.id)
        assert loaded is not None
        loaded.remove_language(world.bm)
        await uow.qasets.save(loaded)
    assert await _count(migrated_engine, "validations") == 1

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.delete(world.qaset.id)
    assert await _count(migrated_engine, "validations") == 0
    assert await _count(migrated_engine, "validation_events") == 0


async def test_find_qaset_by_item(migrated_engine: AsyncEngine) -> None:
    world = await _world(migrated_engine)
    bm = world.qaset.presence(world.bm)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        by_answer = await uow.qasets.find_by_answer(bm.answer.id)
        by_variant = await uow.qasets.find_by_variant(bm.variants[0].id)
        assert await uow.qasets.find_by_answer(uuid4()) is None
    assert by_answer is not None
    assert by_variant is not None
    assert by_answer.id == by_variant.id == world.qaset.id
