from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from qa_authoring.application.language_errors import LanguageCodeAlreadyExistsError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_round_trips_a_language(migrated_engine: AsyncEngine) -> None:
    language = Language.register(LanguageCode("bm_fr"), "Bambara (French)")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(language)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.languages.get(language.id)
        by_code = await uow.languages.find_by_code(LanguageCode("bm_fr"))

    assert loaded is not None
    assert (loaded.id, loaded.code, loaded.name) == (language.id, language.code, language.name)
    assert by_code == loaded


async def test_lists_ordered_by_code(migrated_engine: AsyncEngine) -> None:
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(Language.register(LanguageCode("fr"), "French"))
        await uow.languages.add(Language.register(LanguageCode("bm"), "Bambara"))

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        codes = [language.code.value for language in await uow.languages.list()]

    assert codes == ["bm", "fr"]


async def test_updates_and_deletes(migrated_engine: AsyncEngine) -> None:
    language = Language.register(LanguageCode("fr"), "French")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(language)

    language.rename("Français")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.update(language)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        renamed = await uow.languages.get(language.id)
    assert renamed is not None
    assert renamed.name == "Français"

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.delete(language.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.languages.get(language.id) is None


async def test_unique_constraint_maps_to_the_duplicate_error(migrated_engine: AsyncEngine) -> None:
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(Language.register(LanguageCode("fr"), "French"))

    with pytest.raises(LanguageCodeAlreadyExistsError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.languages.add(Language.register(LanguageCode("fr"), "Français"))

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert len(await uow.languages.list()) == 1


async def test_a_failed_unit_of_work_rolls_back(migrated_engine: AsyncEngine) -> None:
    with pytest.raises(RuntimeError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.languages.add(Language.register(LanguageCode("fr"), "French"))
            raise RuntimeError("boom")

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.languages.list() == ()


async def test_table_lives_in_the_app_schema(migrated_engine: AsyncEngine) -> None:
    query = text(
        "SELECT table_schema FROM information_schema.tables WHERE table_name = 'languages'"
    )
    async with migrated_engine.connect() as connection:
        schemas: list[str] = list((await connection.execute(query)).scalars())
    assert "qa_authoring_repo_it" in schemas
    assert "public" not in schemas
