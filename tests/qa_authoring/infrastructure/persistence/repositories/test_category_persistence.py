from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.category_errors import CategoryInUseError
from qa_authoring.domain.model.category import Category
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


async def _qaset(engine: AsyncEngine) -> QASet:
    fr = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="a")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
    return qaset


async def _register(engine: AsyncEngine, name: str) -> tuple[Category, bool]:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        return await uow.categories.get_or_create(Category.register(name))


async def _add(engine: AsyncEngine, qaset_id: UUID, category_id: UUID) -> None:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        qaset = await uow.qasets.get(qaset_id)
        assert qaset is not None
        qaset.add_category(category_id)
        await uow.qasets.save(qaset)


async def _attachments(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text("SELECT count(*) FROM qaset_categories")) or 0)


async def test_catalogue_round_trip_and_get_or_create(migrated_engine: AsyncEngine) -> None:
    created, was_created = await _register(migrated_engine, " Malaria ")
    again, created_again = await _register(migrated_engine, "MALARIA")
    await _register(migrated_engine, "Nutrition")

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.categories.get(created.id)
        listed = await uow.categories.list()
        prefixed = await uow.categories.list("  MAL")
        many = await uow.categories.get_many({created.id, uuid4()})

    assert (was_created, created_again) == (True, False)
    assert again.id == created.id
    assert loaded is not None
    assert (loaded.id, loaded.name, loaded.key) == (created.id, "Malaria", "malaria")
    assert [c.name for c in listed] == ["Malaria", "Nutrition"]
    assert [c.id for c in prefixed] == [created.id]
    assert list(many) == [created.id]


async def test_normalized_key_is_unique_at_db_level(migrated_engine: AsyncEngine) -> None:
    await _register(migrated_engine, "Malaria")
    with pytest.raises(IntegrityError, match="uq_categories_key"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO categories (id, name, key) VALUES (:id, 'MALARIA', 'malaria')"),
                {"id": uuid4()},
            )


async def test_prefix_filter_escapes_like_wildcards(migrated_engine: AsyncEngine) -> None:
    await _register(migrated_engine, "100% covered")
    await _register(migrated_engine, "100 percent")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert [c.name for c in await uow.categories.list("100%")] == ["100% covered"]
        assert [c.name for c in await uow.categories.list("10_")] == []


async def test_attachment_round_trip_in_order(migrated_engine: AsyncEngine) -> None:
    qaset = await _qaset(migrated_engine)
    ids = [(await _register(migrated_engine, n))[0].id for n in ("c cat", "a cat", "b cat")]
    for category_id in ids:
        await _add(migrated_engine, qaset.id, category_id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        listed = await uow.qasets.list_by_theme(qaset.theme_id)
        assert await uow.qasets.uses_category(ids[0])
        assert loaded is not None
        assert loaded.category_ids == tuple(ids)
        assert listed[0].category_ids == tuple(ids)
        loaded.remove_category(ids[1])
        await uow.qasets.save(loaded)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        reloaded = await uow.qasets.get(qaset.id)
        assert not await uow.qasets.uses_category(ids[1])
    assert reloaded is not None
    assert reloaded.category_ids == (ids[0], ids[2])


async def test_delete_attached_category_is_restricted(migrated_engine: AsyncEngine) -> None:
    qaset = await _qaset(migrated_engine)
    category, _ = await _register(migrated_engine, "Malaria")
    await _add(migrated_engine, qaset.id, category.id)

    with pytest.raises(CategoryInUseError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.categories.delete(category.id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.categories.get(category.id) is not None


async def test_deleting_the_qaset_cascades_its_attachments(migrated_engine: AsyncEngine) -> None:
    qaset = await _qaset(migrated_engine)
    category, _ = await _register(migrated_engine, "Malaria")
    await _add(migrated_engine, qaset.id, category.id)
    assert await _attachments(migrated_engine) == 1

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.delete(qaset.id)

    assert await _attachments(migrated_engine) == 0
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.categories.delete(category.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.categories.get(category.id) is None
