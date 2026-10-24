from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from config.container import Container
from qa_authoring.application.list_validation_queues.command import ValidationQueueQuery
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import AudioReference, QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.user import User
from qa_authoring.domain.model.validation import Validation, ValidationState, ValidationSubject
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import AUDIO_POLICY, NOW, FakeAudioProbe, InMemoryAudioStorage

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

VALIDATED, REJECTED = ValidationState.VALIDATED, ValidationState.REJECTED


def _audio(name: str) -> AudioReference:
    return AudioReference(
        id=uuid4(),
        storage_uri=f"memory://audio/{name}",
        mime_type="audio/webm",
        duration_ms=1000,
        checksum_sha256=hashlib.sha256(name.encode()).hexdigest(),
        size_bytes=10,
        created_at=NOW,
    )


@dataclass
class World:
    """Project P1 (base fr): theme T1 holds q1 (validated) and q2 (rejected), theme T2 holds q3
    (Bambara only) and q5 (reset to pending). Project P2 holds q4 (never decided)."""

    container: Container
    p1: Project
    p2: Project
    t1: Theme
    t2: Theme
    q1: QASet
    q2: QASet
    q3: QASet
    q4: QASet
    q5: QASet
    ids: dict[str, UUID]
    fr: UUID

    async def run(self, build: Callable[[Any], Any], **query: Any) -> Any:
        return await self.container.run(build, ValidationQueueQuery(**query))


@pytest.fixture
async def world(migrated_engine: AsyncEngine) -> World:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    p1 = Project.create(name="Muso", base_language_id=fr.id)
    p2 = Project.create(name="Other", base_language_id=fr.id)
    pr1 = Protocol.create(project_id=p1.id, name="Malaria")
    pr2 = Protocol.create(project_id=p2.id, name="Nutrition")
    t1 = Theme.create(protocol_id=pr1.id, name="Fever")
    t2 = Theme.create(protocol_id=pr1.id, name="Prevention")
    t3 = Theme.create(protocol_id=pr2.id, name="Diet")
    reviewer = User.create(email="reviewer@example.org", display_name="Reviewer")

    q1 = QASet.create(theme_id=t1.id, language_id=fr.id, answer_text="A1")
    v1a = q1.add_variant(fr.id, "V1a")
    q1.add_variant(fr.id, "V1b")
    b1 = q1.add_language(bm.id, "B1")
    bv1 = q1.add_variant(bm.id, "BV1")
    bv1b = q1.add_variant(bm.id, "BV1b")
    q1.link_answers(q1.answers[0].id, b1.id)
    q1.link_variants(v1a.id, bv1.id)
    q1_audio, bv1_audio = _audio("a1"), _audio("bv1")
    q1.set_answer_audio(q1.answers[0].id, q1_audio)
    q1.set_variant_audio(bv1.id, bv1_audio)

    q2 = QASet.create(theme_id=t1.id, language_id=fr.id, answer_text="A2")
    b2 = q2.add_language(bm.id, "B2")
    b2_audio = _audio("b2")
    q2.set_answer_audio(b2.id, b2_audio)

    q3 = QASet.create(theme_id=t2.id, language_id=bm.id, answer_text="B3")
    q4 = QASet.create(theme_id=t3.id, language_id=fr.id, answer_text="A4")
    q5 = QASet.create(theme_id=t2.id, language_id=fr.id, answer_text="A5")

    def start(subject: ValidationSubject, state: ValidationState) -> Validation:
        return Validation.start(subject, state, actor_user_id=reviewer.id, at=NOW)

    reset = start(ValidationSubject.for_qaset(q5.id), VALIDATED)
    reset.reset(actor_user_id=reviewer.id, at=NOW)
    decided = [
        start(ValidationSubject.for_qaset(q1.id), VALIDATED),
        start(ValidationSubject.for_qaset(q2.id), REJECTED),
        reset,
        start(ValidationSubject.for_variant(bv1.id), VALIDATED),
        start(ValidationSubject.for_answer(b2.id), REJECTED),
        start(ValidationSubject.for_audio(q1_audio.id), VALIDATED),
        start(ValidationSubject.for_audio(b2_audio.id), REJECTED),
    ]
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(fr)
        await uow.languages.add(bm)
        await uow.users.add(reviewer)
        for project in (p1, p2):
            await uow.projects.add(project)
        for protocol in (pr1, pr2):
            await uow.protocols.add(protocol)
        for theme in (t1, t2, t3):
            await uow.themes.add(theme)
        for qaset in (q1, q2, q3, q4, q5):
            await uow.qasets.add(qaset)
        for validation in decided:
            await uow.validations.add(validation)

    container = Container(
        partial(SqlAlchemyUnitOfWork, migrated_engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
    )
    ids = {
        "a1": q1.answers[0].id,
        "v1a": v1a.id,
        "b1": b1.id,
        "bv1": bv1.id,
        "bv1b": bv1b.id,
        "b2": b2.id,
        "b3": q3.answers[0].id,
        "q1_audio": q1_audio.id,
        "bv1_audio": bv1_audio.id,
        "b2_audio": b2_audio.id,
    }
    return World(container, p1, p2, t1, t2, q1, q2, q3, q4, q5, ids, fr.id)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("pending", {"q4", "q5"}),
        ("rejected", {"q2"}),
        ("validated", {"q1"}),
        ("all", {"q1", "q2", "q4", "q5"}),
    ],
)
async def test_clinical_queue_by_state(world: World, state: str, expected: set[str]) -> None:
    page = await world.run(world.container.build_list_clinical_queue, state=state)
    assert {item.qaset_id for item in page.items} == {getattr(world, q).id for q in expected}
    assert page.total == len(expected)


async def test_clinical_items_carry_their_context(world: World) -> None:
    page = await world.run(world.container.build_list_clinical_queue, state="validated")
    [item] = page.items
    assert (item.context.project.id, item.context.project.name) == (world.p1.id, "Muso")
    assert item.context.protocol.name == "Malaria"
    assert (item.context.theme.id, item.context.theme.name) == (world.t1.id, "Fever")
    assert (item.base_language_code, item.answer_text) == ("fr", "A1")
    async with world.container.unit_of_work() as uow:
        stored = await uow.qasets.get(world.q1.id)
    assert stored is not None
    # The repository's order; variants saved in one transaction tie on created_at.
    assert item.variant_texts == tuple(v.text for v in stored.presence(world.fr).variants)
    assert sorted(item.variant_texts) == ["V1a", "V1b"]
    assert item.state == "validated"
    pending = await world.run(world.container.build_list_clinical_queue)
    assert {item.state for item in pending.items} == {"pending"}


async def test_clinical_queue_scoping(world: World) -> None:
    by_project = await world.run(world.container.build_list_clinical_queue, project_id=world.p2.id)
    by_theme = await world.run(
        world.container.build_list_clinical_queue, theme_id=world.t2.id, state="all"
    )
    assert [item.qaset_id for item in by_project.items] == [world.q4.id]
    assert [item.qaset_id for item in by_theme.items] == [world.q5.id]


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("pending", {"b1", "bv1b", "b3"}),
        ("rejected", {"b2"}),
        ("validated", {"bv1"}),
        ("all", {"b1", "bv1", "bv1b", "b2", "b3"}),
    ],
)
async def test_translation_queue_excludes_the_base_language(
    world: World, state: str, expected: set[str]
) -> None:
    page = await world.run(world.container.build_list_translation_queue, state=state)
    assert {item.item_id for item in page.items} == {world.ids[i] for i in expected}
    assert page.total == len(expected)


async def test_translation_items_carry_their_source(world: World) -> None:
    page = await world.run(world.container.build_list_translation_queue, state="all")
    items = {item.item_id: item for item in page.items}
    answer, variant = items[world.ids["b1"]], items[world.ids["bv1"]]
    assert (answer.kind, answer.language_code, answer.text) == ("answer", "bm", "B1")
    assert [(s.item_id, s.text) for s in answer.sources] == [(world.ids["a1"], "A1")]
    assert answer.fallback_base_answer_text is None
    assert (variant.kind, variant.state) == ("variant", "validated")
    assert [(s.item_id, s.text) for s in variant.sources] == [(world.ids["v1a"], "V1a")]
    unlinked = items[world.ids["bv1b"]]
    assert (unlinked.sources, unlinked.fallback_base_answer_text) == ((), "A1")
    no_base = items[world.ids["b3"]]
    assert (no_base.sources, no_base.fallback_base_answer_text) == ((), None)
    assert answer.qaset_id == world.q1.id
    assert (answer.context.project.name, answer.context.theme.name) == ("Muso", "Fever")


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("pending", {"bv1_audio"}),
        ("rejected", {"b2_audio"}),
        ("validated", {"q1_audio"}),
        ("all", {"q1_audio", "bv1_audio", "b2_audio"}),
    ],
)
async def test_audio_queue_by_state(world: World, state: str, expected: set[str]) -> None:
    page = await world.run(world.container.build_list_audio_queue, state=state)
    assert {item.audio_id for item in page.items} == {world.ids[a] for a in expected}
    assert page.total == len(expected)


async def test_audio_items_carry_their_item(world: World) -> None:
    page = await world.run(world.container.build_list_audio_queue, state="all")
    items = {item.audio_id: item for item in page.items}
    variant, answer = items[world.ids["bv1_audio"]], items[world.ids["q1_audio"]]
    assert (variant.item_kind, variant.item_id, variant.language_code, variant.text) == (
        "variant",
        world.ids["bv1"],
        "bm",
        "BV1",
    )
    assert (answer.item_kind, answer.item_id, answer.language_code, answer.text) == (
        "answer",
        world.ids["a1"],
        "fr",
        "A1",
    )
    assert (variant.qaset_id, variant.state, answer.state) == (world.q1.id, "pending", "validated")
    assert variant.context.theme.name == "Fever"
    scoped = await world.run(
        world.container.build_list_audio_queue, state="all", theme_id=world.t2.id
    )
    assert scoped.items == () and scoped.total == 0


@pytest.mark.parametrize(
    "build", ["build_list_clinical_queue", "build_list_translation_queue", "build_list_audio_queue"]
)
async def test_keyset_pagination(world: World, build: str) -> None:
    collected: list[Any] = []
    cursor: str | None = None
    totals = set()
    while True:
        page = await world.run(getattr(world.container, build), state="all", limit=2, cursor=cursor)
        collected.extend(page.items)
        totals.add(page.total)
        assert len(page.items) <= 2
        if page.next_cursor is None:
            break
        cursor = str(page.next_cursor)
    full = await world.run(getattr(world.container, build), state="all")
    assert collected == list(full.items)
    assert totals == {len(full.items)}
    keys = [
        getattr(i, "audio_id", None) or getattr(i, "item_id", None) or i.qaset_id for i in collected
    ]
    assert keys == sorted(keys)
