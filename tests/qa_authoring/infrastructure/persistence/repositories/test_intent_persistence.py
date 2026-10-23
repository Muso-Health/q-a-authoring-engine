from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from qa_authoring.application.intent_errors import IntentInUseError
from qa_authoring.domain.model.intent import Intent
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


async def _qaset_with_variant(engine: AsyncEngine) -> tuple[QASet, UUID, UUID]:
    fr = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="a")
    variant = qaset.add_variant(fr.id, "q")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
    return qaset, variant.id, fr.id


async def _register(engine: AsyncEngine, intent_text: str) -> tuple[Intent, bool]:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        return await uow.intents.get_or_create(Intent.register(intent_text))


async def _attach(engine: AsyncEngine, qaset_id: UUID, variant_id: UUID, intent_id: UUID) -> None:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        qaset = await uow.qasets.get(qaset_id)
        assert qaset is not None
        qaset.attach_intent(variant_id, intent_id)
        await uow.qasets.save(qaset)


async def test_catalogue_round_trip_and_get_or_create(migrated_engine: AsyncEngine) -> None:
    created, was_created = await _register(migrated_engine, " Dosage ")
    again, created_again = await _register(migrated_engine, "DOSAGE")
    await _register(migrated_engine, "Side effects")

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.intents.get(created.id)
        listed = await uow.intents.list()
        prefixed = await uow.intents.list("  DOS")
        many = await uow.intents.get_many({created.id, uuid4()})

    assert (was_created, created_again) == (True, False)
    assert again.id == created.id
    assert loaded is not None
    assert (loaded.id, loaded.text, loaded.key) == (created.id, "Dosage", "dosage")
    assert [i.text for i in listed] == ["Dosage", "Side effects"]
    assert [i.id for i in prefixed] == [created.id]
    assert list(many) == [created.id]


async def test_normalized_key_is_unique_at_db_level(migrated_engine: AsyncEngine) -> None:
    await _register(migrated_engine, "Dosage")
    with pytest.raises(IntegrityError, match="uq_intents_key"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO intents (id, text, key) VALUES (:id, 'DOSAGE', 'dosage')"),
                {"id": uuid4()},
            )


async def test_prefix_filter_escapes_like_wildcards(migrated_engine: AsyncEngine) -> None:
    await _register(migrated_engine, "100% safe")
    await _register(migrated_engine, "100 percent")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert [i.text for i in await uow.intents.list("100%")] == ["100% safe"]
        assert [i.text for i in await uow.intents.list("10_")] == []


async def test_attachment_round_trip_in_order(migrated_engine: AsyncEngine) -> None:
    qaset, variant_id, _ = await _qaset_with_variant(migrated_engine)
    first, _ = await _register(migrated_engine, "Side effects")
    second, _ = await _register(migrated_engine, "Dosage")
    await _attach(migrated_engine, qaset.id, variant_id, first.id)
    await _attach(migrated_engine, qaset.id, variant_id, second.id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        assert await uow.qasets.uses_intent(first.id)
        assert loaded is not None
        loaded.detach_intent(variant_id, first.id)
        await uow.qasets.save(loaded)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        reloaded = await uow.qasets.get(qaset.id)
        assert not await uow.qasets.uses_intent(first.id)
    assert loaded.variants[0].intent_ids == (second.id,)
    assert reloaded is not None
    assert reloaded.variants[0].intent_ids == (second.id,)


async def test_attachment_order_survives_reload(migrated_engine: AsyncEngine) -> None:
    qaset, variant_id, _ = await _qaset_with_variant(migrated_engine)
    texts = ["c intent", "a intent", "b intent"]
    ids = [(await _register(migrated_engine, t))[0].id for t in texts]
    for intent_id in ids:
        await _attach(migrated_engine, qaset.id, variant_id, intent_id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
    assert loaded is not None
    assert loaded.variants[0].intent_ids == tuple(ids)


async def test_delete_attached_intent_is_restricted(migrated_engine: AsyncEngine) -> None:
    qaset, variant_id, _ = await _qaset_with_variant(migrated_engine)
    intent, _ = await _register(migrated_engine, "Dosage")
    await _attach(migrated_engine, qaset.id, variant_id, intent.id)

    with pytest.raises(IntentInUseError):
        async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
            await uow.intents.delete(intent.id)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.intents.get(intent.id) is not None


async def test_deleting_the_variant_cascades_its_attachments(
    migrated_engine: AsyncEngine,
) -> None:
    qaset, variant_id, _ = await _qaset_with_variant(migrated_engine)
    intent, _ = await _register(migrated_engine, "Dosage")
    await _attach(migrated_engine, qaset.id, variant_id, intent.id)

    async with migrated_engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM question_variants WHERE id = :id"), {"id": variant_id}
        )
        count = await connection.scalar(text("SELECT count(*) FROM variant_intents"))
    assert count == 0

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.intents.delete(intent.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        assert await uow.intents.get(intent.id) is None
