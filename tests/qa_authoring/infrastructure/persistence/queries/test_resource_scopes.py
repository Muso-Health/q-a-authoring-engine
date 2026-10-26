from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from qa_authoring.application.ports.resource_scopes import ResourceKind, ResourceScope
from qa_authoring.domain.model.documentation import Documentation
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import AudioReference, QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import NOW, in_memory_container

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from qa_authoring.application.ports.resource_scopes import ResourceScopes

pytestmark = pytest.mark.integration


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


async def test_every_resource_resolves_to_its_project_and_item_language(
    migrated_engine: AsyncEngine,
) -> None:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="Muso", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Malaria")
    theme = Theme.create(protocol_id=protocol.id, name="Fever")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="A")
    bm_answer = qaset.add_language(bm.id, "B")
    variant = qaset.add_variant(bm.id, "BV")
    answer_audio, variant_audio = _audio("a"), _audio("v")
    qaset.set_answer_audio(bm_answer.id, answer_audio)
    qaset.set_variant_audio(variant.id, variant_audio)
    document = Documentation.create(
        theme_id=theme.id,
        filename="guide.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        checksum_sha256="0" * 64,
        storage_uri="memory://documentation/x",
        at=NOW,
    )
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(fr)
        await uow.languages.add(bm)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
        await uow.documentation.add(document)

    expected = {
        (ResourceKind.PROJECT, project.id): ResourceScope(project.id),
        (ResourceKind.PROTOCOL, protocol.id): ResourceScope(project.id),
        (ResourceKind.THEME, theme.id): ResourceScope(project.id),
        (ResourceKind.DOCUMENTATION, document.id): ResourceScope(project.id),
        (ResourceKind.QASET, qaset.id): ResourceScope(project.id),
        (ResourceKind.ANSWER, qaset.answers[0].id): ResourceScope(project.id, fr.id),
        (ResourceKind.ANSWER, bm_answer.id): ResourceScope(project.id, bm.id),
        (ResourceKind.VARIANT, variant.id): ResourceScope(project.id, bm.id),
        (ResourceKind.AUDIO, answer_audio.id): ResourceScope(project.id, bm.id),
        (ResourceKind.AUDIO, variant_audio.id): ResourceScope(project.id, bm.id),
    }
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        resolved = {key: await uow.resource_scopes.resolve(*key) for key in expected}
        missing = [await uow.resource_scopes.resolve(kind, uuid4()) for kind in ResourceKind]
    assert resolved == expected
    assert missing == [None] * len(ResourceKind)

    # The in-memory resolver the API tests use agrees with the SQL one.
    _, store = in_memory_container()
    await store.projects.add(project)
    await store.protocols.add(protocol)
    await store.themes.add(theme)
    await store.qasets.add(qaset)
    await store.documentation.add(document)
    fake: ResourceScopes = store.resource_scopes
    assert {key: await fake.resolve(*key) for key in expected} == expected
