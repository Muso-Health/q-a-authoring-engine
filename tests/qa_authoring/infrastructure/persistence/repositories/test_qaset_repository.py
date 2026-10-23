from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.language_errors import LanguageInUseError
from qa_authoring.application.qaset_errors import UnknownLanguageError
from qa_authoring.application.theme_errors import ThemeHasQASetsError, ThemeNotFoundError
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


async def _seed(engine: AsyncEngine) -> tuple[UUID, UUID, UUID]:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.languages.add(bm)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
    return theme.id, fr.id, bm.id


def _snapshot(qaset: QASet) -> object:
    return (
        qaset.id,
        qaset.theme_id,
        [
            (
                p.language_id,
                p.answer.id,
                p.answer.text,
                sorted((v.id, v.text) for v in p.variants),
            )
            for p in qaset.presences()
        ],
    )


async def test_round_trips_a_multilingual_aggregate(migrated_engine: AsyncEngine) -> None:
    theme_id, fr, bm = await _seed(migrated_engine)
    qaset = QASet.create(theme_id=theme_id, language_id=fr, answer_text="Rest.")
    qaset.add_language(bm, "Bambara answer")
    qaset.add_variant(fr, "What to do?")
    qaset.add_variant(fr, "How to treat it?")
    qaset.add_variant(bm, "Bambara question")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(qaset)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        listed = await uow.qasets.list_by_theme(theme_id)
        assert await uow.qasets.exists_for_theme(theme_id)
        assert await uow.qasets.uses_language(bm)

    assert loaded is not None
    assert _snapshot(loaded) == _snapshot(qaset)
    assert [_snapshot(q) for q in listed] == [_snapshot(qaset)]


async def test_save_applies_every_change_to_the_aggregate(migrated_engine: AsyncEngine) -> None:
    theme_id, fr, bm = await _seed(migrated_engine)
    qaset = QASet.create(theme_id=theme_id, language_id=fr, answer_text="Rest.")
    dropped = qaset.add_variant(fr, "Old question")
    qaset.add_language(bm, "Bambara answer")
    qaset.add_variant(bm, "Bambara question")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(qaset)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        assert loaded is not None
        loaded.update_answer(fr, "Drink water.")
        loaded.remove_variant(dropped.id)
        loaded.add_variant(fr, "New question")
        loaded.remove_language(bm)
        await uow.qasets.save(loaded)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        reloaded = await uow.qasets.get(qaset.id)
        assert not await uow.qasets.uses_language(bm)
    assert reloaded is not None
    assert _snapshot(reloaded) == _snapshot(loaded)


async def test_delete_cascades_within_the_aggregate(migrated_engine: AsyncEngine) -> None:
    theme_id, fr, _ = await _seed(migrated_engine)
    qaset = QASet.create(theme_id=theme_id, language_id=fr, answer_text="Rest.")
    qaset.add_variant(fr, "Q?")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(qaset)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.delete(qaset.id)

    async with migrated_engine.connect() as connection:
        counts = [
            await connection.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in ("qasets", "answers", "question_variants")
        ]
    assert counts == [0, 0, 0]


async def test_unique_answer_per_language_at_db_level(migrated_engine: AsyncEngine) -> None:
    theme_id, fr, _ = await _seed(migrated_engine)
    qaset = QASet.create(theme_id=theme_id, language_id=fr, answer_text="Rest.")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(qaset)

    with pytest.raises(IntegrityError, match="uq_answers_qaset_id_language_id"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO answers (id, qaset_id, language_id, text) "
                    "VALUES (:id, :qaset_id, :language_id, 'dup')"
                ),
                {"id": uuid4(), "qaset_id": qaset.id, "language_id": fr},
            )


async def test_variant_without_presence_is_rejected_at_db_level(
    migrated_engine: AsyncEngine,
) -> None:
    theme_id, fr, bm = await _seed(migrated_engine)
    qaset = QASet.create(theme_id=theme_id, language_id=fr, answer_text="Rest.")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(qaset)

    with pytest.raises(IntegrityError, match="fk_question_variants_qaset_id_answers"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO question_variants (id, qaset_id, language_id, text) "
                    "VALUES (:id, :qaset_id, :language_id, 'orphan')"
                ),
                {"id": uuid4(), "qaset_id": qaset.id, "language_id": bm},
            )


async def test_fk_rules_map_to_domain_errors(migrated_engine: AsyncEngine) -> None:
    theme_id, fr, bm = await _seed(migrated_engine)

    with pytest.raises(ThemeNotFoundError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.qasets.add(QASet.create(theme_id=uuid4(), language_id=fr, answer_text="x"))
    with pytest.raises(UnknownLanguageError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.qasets.add(
                QASet.create(theme_id=theme_id, language_id=uuid4(), answer_text="x")
            )

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(QASet.create(theme_id=theme_id, language_id=bm, answer_text="x"))
    with pytest.raises(ThemeHasQASetsError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.themes.delete(theme_id)
    with pytest.raises(LanguageInUseError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.languages.delete(bm)
