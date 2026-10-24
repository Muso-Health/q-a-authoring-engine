from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from config.container import Container
from qa_authoring.application.delete_documentation.command import DeleteDocumentationCommand
from qa_authoring.application.list_documentation.command import ListDocumentationQuery
from qa_authoring.application.upload_documentation.command import UploadDocumentationCommand
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from qa_authoring.infrastructure.storage.local import LocalBlobStorage
from tests.fakes import (
    AUDIO_POLICY,
    DOCUMENTATION_POLICY,
    NOW,
    FakeAudioProbe,
    InMemoryAudioStorage,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def _theme(engine: AsyncEngine) -> Theme:
    fr = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
    return theme


def _container(engine: AsyncEngine, storage: LocalBlobStorage) -> Container:
    return Container(
        partial(SqlAlchemyUnitOfWork, engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
        clock=lambda: NOW,
        documentation_storage=storage,
        documentation_policy=DOCUMENTATION_POLICY,
    )


async def _count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text("SELECT count(*) FROM documentation")) or 0)


async def test_documentation_round_trip_with_local_storage(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    theme = await _theme(migrated_engine)
    storage = LocalBlobStorage(tmp_path / "docs", "documentation/")
    container = _container(migrated_engine, storage)

    uploaded = await container.run(
        container.build_upload_documentation,
        UploadDocumentationCommand(theme.id, b"Malaria.", "guide.txt", "text/plain"),
    )
    listed = await container.run(
        container.build_list_documentation, ListDocumentationQuery(theme.id)
    )

    assert [d.id for d in listed] == [uploaded.id]
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        stored = await uow.documentation.get(uploaded.id)
        assert stored is not None
        assert await uow.documentation.storage_uri_in_use(stored.storage_uri)
    assert (stored.filename, stored.mime_type, stored.size_bytes, stored.created_at) == (
        "guide.txt",
        "text/plain",
        8,
        NOW,
    )
    assert await storage.read(stored.storage_uri) == b"Malaria."

    await container.run(
        container.build_delete_documentation, DeleteDocumentationCommand(theme.id, uploaded.id)
    )
    assert await _count(migrated_engine) == 0
    assert not list((tmp_path / "docs").rglob("*.*")) and not any(
        p.is_file() for p in (tmp_path / "docs").rglob("*")
    )


async def test_deleting_the_theme_cascades_its_documentation(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    theme = await _theme(migrated_engine)
    container = _container(migrated_engine, LocalBlobStorage(tmp_path / "docs", "documentation/"))
    for name in ("a.txt", "b.txt"):
        await container.run(
            container.build_upload_documentation,
            UploadDocumentationCommand(theme.id, name.encode(), name, "text/plain"),
        )
    assert await _count(migrated_engine) == 2

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.themes.delete(theme.id)

    assert await _count(migrated_engine) == 0
