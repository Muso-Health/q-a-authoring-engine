from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config.container import Container
from qa_authoring.application.set_variant_audio.command import SetVariantAudioCommand
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import AudioReference, QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import AUDIO_POLICY, NOW, FakeAudioProbe, InMemoryAudioStorage

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


def _audio(uri: str = "memory://audio/abc") -> AudioReference:
    return AudioReference(
        id=uuid4(),
        storage_uri=uri,
        mime_type="audio/webm",
        duration_ms=1500,
        checksum_sha256="b" * 64,
        size_bytes=1234,
        created_at=datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
    )


async def _qaset(engine: AsyncEngine) -> tuple[QASet, UUID]:
    fr = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="a")
    qaset.add_variant(fr.id, "q")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
    return qaset, fr.id


async def _change(engine: AsyncEngine, qaset_id: UUID, mutate: object) -> QASet:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        qaset = await uow.qasets.get(qaset_id)
        assert qaset is not None
        mutate(qaset)  # type: ignore[operator]
        await uow.qasets.save(qaset)
    return qaset


async def _count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text("SELECT count(*) FROM audios")) or 0)


async def test_round_trips_audio_references(migrated_engine: AsyncEngine) -> None:
    qaset, _ = await _qaset(migrated_engine)
    answer_audio, variant_audio = _audio("memory://a"), _audio("memory://v")
    await _change(
        migrated_engine,
        qaset.id,
        lambda q: (
            q.set_answer_audio(q.answers[0].id, answer_audio),
            q.set_variant_audio(q.variants[0].id, variant_audio),
        ),
    )

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        found = await uow.qasets.find_audio(variant_audio.id)
        assert await uow.qasets.storage_uri_in_use("memory://a")
        assert not await uow.qasets.storage_uri_in_use("memory://nothing")

    assert loaded is not None
    assert loaded.answers[0].audio == answer_audio
    assert loaded.variants[0].audio == variant_audio
    assert found == variant_audio


async def test_replace_and_remove_persist(migrated_engine: AsyncEngine) -> None:
    qaset, _ = await _qaset(migrated_engine)
    first, second = _audio(), _audio()
    await _change(migrated_engine, qaset.id, lambda q: q.set_answer_audio(q.answers[0].id, first))
    await _change(migrated_engine, qaset.id, lambda q: q.set_answer_audio(q.answers[0].id, second))

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
        assert await uow.qasets.find_audio(first.id) is None
    assert loaded is not None
    assert loaded.answers[0].audio == second

    await _change(migrated_engine, qaset.id, lambda q: q.remove_answer_audio(q.answers[0].id))
    assert await _count(migrated_engine) == 0


async def test_exactly_one_target_is_checked(migrated_engine: AsyncEngine) -> None:
    qaset, _ = await _qaset(migrated_engine)
    insert = text(
        "INSERT INTO audios (id, answer_id, variant_id, storage_uri, mime_type, duration_ms, "
        "checksum_sha256, size_bytes, created_at) VALUES (:id, :answer_id, :variant_id, 'u', "
        "'audio/webm', 1, :checksum, 1, now())"
    )
    for answer_id, variant_id in ((None, None), (qaset.answers[0].id, qaset.variants[0].id)):
        with pytest.raises(IntegrityError, match="ck_audios_exactly_one_target"):
            async with migrated_engine.begin() as connection:
                await connection.execute(
                    insert,
                    {
                        "id": uuid4(),
                        "answer_id": answer_id,
                        "variant_id": variant_id,
                        "checksum": "c" * 64,
                    },
                )


async def test_one_audio_per_item(migrated_engine: AsyncEngine) -> None:
    qaset, _ = await _qaset(migrated_engine)
    await _change(
        migrated_engine, qaset.id, lambda q: q.set_variant_audio(q.variants[0].id, _audio())
    )

    with pytest.raises(IntegrityError, match="uq_audios_variant_id"):
        async with migrated_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO audios (id, variant_id, storage_uri, mime_type, duration_ms, "
                    "checksum_sha256, size_bytes, created_at) VALUES (:id, :variant_id, 'u', "
                    "'audio/webm', 1, :checksum, 1, now())"
                ),
                {"id": uuid4(), "variant_id": qaset.variants[0].id, "checksum": "c" * 64},
            )


async def test_deleting_items_cascades_their_audio(migrated_engine: AsyncEngine) -> None:
    qaset, fr = await _qaset(migrated_engine)
    await _change(
        migrated_engine,
        qaset.id,
        lambda q: (
            q.set_answer_audio(q.answers[0].id, _audio()),
            q.set_variant_audio(q.variants[0].id, _audio()),
        ),
    )
    async with migrated_engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM question_variants WHERE id = :id"), {"id": qaset.variants[0].id}
        )
    assert await _count(migrated_engine) == 1

    await _change(migrated_engine, qaset.id, lambda q: q.remove_language(fr))
    assert await _count(migrated_engine) == 0


async def test_upload_use_case_commits_before_deleting_the_old_blob(
    migrated_engine: AsyncEngine,
) -> None:
    qaset, _ = await _qaset(migrated_engine)
    storage = InMemoryAudioStorage()
    container = Container(
        partial(SqlAlchemyUnitOfWork, migrated_engine),
        audio_storage=storage,
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
        clock=lambda: NOW,
    )

    async def upload(content: bytes) -> None:
        command = SetVariantAudioCommand(
            qaset_id=qaset.id, variant_id=qaset.variants[0].id, content=content, client_mime=None
        )
        await container.run(container.build_set_variant_audio, command)

    await upload(b"first")
    [first_uri] = storage.blobs
    await upload(b"second")

    assert first_uri not in storage.blobs
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
    assert loaded is not None
    reference = loaded.variants[0].audio
    assert reference is not None
    assert list(storage.blobs) == [reference.storage_uri]
