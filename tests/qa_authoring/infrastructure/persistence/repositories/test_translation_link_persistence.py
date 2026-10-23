from __future__ import annotations

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
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def _linked_qaset(engine: AsyncEngine) -> tuple[QASet, UUID, UUID]:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="fr")
    qaset.add_language(bm.id, "bm")
    fr_variant = qaset.add_variant(fr.id, "fr q")
    bm_one = qaset.add_variant(bm.id, "bm q1")
    bm_two = qaset.add_variant(bm.id, "bm q2")
    qaset.link_answers(qaset.presence(bm.id).answer.id, qaset.presence(fr.id).answer.id)
    qaset.link_variants(fr_variant.id, bm_one.id)
    qaset.link_variants(bm_two.id, fr_variant.id)
    async with SqlAlchemyUnitOfWork(engine) as uow:
        for entity in (fr, bm):
            await uow.languages.add(entity)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
    return qaset, fr.id, bm.id


async def _load(engine: AsyncEngine, qaset_id: UUID) -> QASet:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        loaded = await uow.qasets.get(qaset_id)
    assert loaded is not None
    return loaded


def _links(qaset: QASet) -> object:
    # Order-insensitive: links created in one transaction share now().
    return (
        sorted((link.id, link.low_id, link.high_id) for link in qaset.answer_links),
        sorted((link.id, link.low_id, link.high_id) for link in qaset.variant_links),
    )


async def _count(engine: AsyncEngine, table: str) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text(f"SELECT count(*) FROM {table}")) or 0)


async def test_round_trips_links(migrated_engine: AsyncEngine) -> None:
    qaset, _, _ = await _linked_qaset(migrated_engine)

    loaded = await _load(migrated_engine, qaset.id)

    assert _links(loaded) == _links(qaset)
    for link in loaded.answer_links + loaded.variant_links:
        assert link.low_id < link.high_id


async def test_save_adds_and_removes_links(migrated_engine: AsyncEngine) -> None:
    qaset, _, _ = await _linked_qaset(migrated_engine)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        assert loaded is not None
        loaded.unlink_variants(loaded.variant_links[0].id)
        loaded.unlink_answers(loaded.answer_links[0].id)
        await uow.qasets.save(loaded)

    reloaded = await _load(migrated_engine, qaset.id)
    assert _links(reloaded) == _links(loaded)
    assert len(reloaded.variant_links) == 1
    assert reloaded.answer_links == ()


async def test_canonical_pair_is_unique_and_ordered(migrated_engine: AsyncEngine) -> None:
    qaset, _, _ = await _linked_qaset(migrated_engine)
    link = qaset.variant_links[0]
    insert = text(
        "INSERT INTO variant_translation_links (id, qaset_id, variant_low_id, variant_high_id) "
        "VALUES (:id, :qaset_id, :low, :high)"
    )

    with pytest.raises(IntegrityError, match="uq_variant_translation_links"):
        async with migrated_engine.begin() as connection:
            params = {"id": uuid4(), "qaset_id": qaset.id, "low": link.low_id, "high": link.high_id}
            await connection.execute(insert, params)
    with pytest.raises(IntegrityError, match="ck_variant_translation_links_canonical_pair"):
        async with migrated_engine.begin() as connection:
            params = {"id": uuid4(), "qaset_id": qaset.id, "low": link.high_id, "high": link.low_id}
            await connection.execute(insert, params)


async def test_deleting_items_cascades_their_links(migrated_engine: AsyncEngine) -> None:
    qaset, fr, _ = await _linked_qaset(migrated_engine)
    fr_variant = qaset.presence(fr).variants[0].id

    async with migrated_engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM question_variants WHERE id = :id"), {"id": fr_variant}
        )
        await connection.execute(
            text("DELETE FROM answers WHERE id = :id"), {"id": qaset.presence(fr).answer.id}
        )

    assert await _count(migrated_engine, "variant_translation_links") == 0
    assert await _count(migrated_engine, "answer_translation_links") == 0


async def test_removing_a_language_presence_removes_its_links(
    migrated_engine: AsyncEngine,
) -> None:
    qaset, _, bm = await _linked_qaset(migrated_engine)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        assert loaded is not None
        loaded.remove_language(bm)
        await uow.qasets.save(loaded)

    reloaded = await _load(migrated_engine, qaset.id)
    assert _links(reloaded) == ([], [])
    assert await _count(migrated_engine, "variant_translation_links") == 0
    assert await _count(migrated_engine, "answer_translation_links") == 0


async def test_deleting_the_qaset_cascades_its_links(migrated_engine: AsyncEngine) -> None:
    qaset, _, _ = await _linked_qaset(migrated_engine)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.delete(qaset.id)
    assert await _count(migrated_engine, "variant_translation_links") == 0
    assert await _count(migrated_engine, "answer_translation_links") == 0
