from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from config.container import Container
from qa_authoring.application.translate_answer.command import TranslateAnswerCommand
from qa_authoring.application.translate_variant.command import TranslateVariantCommand
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.user import User
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import (
    AUDIO_POLICY,
    NOW,
    FakeAudioProbe,
    FakeGoogleTranslator,
    FakeLlm,
    InMemoryAudioStorage,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_translation_persists_the_item_and_link_unvalidated(
    migrated_engine: AsyncEngine,
) -> None:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="P", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="Buvez de l'eau.")
    variant = qaset.add_variant(fr.id, "Que faire ?")
    author = User.create(email="author@example.org", display_name="Author")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        for language in (fr, bm):
            await uow.languages.add(language)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.qasets.add(qaset)
        await uow.users.add(author)
    container = Container(
        partial(SqlAlchemyUnitOfWork, migrated_engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
        clock=lambda: NOW,
        llm=FakeLlm(),
        google_translator=FakeGoogleTranslator(),
    )

    await container.run(
        container.build_translate_answer,
        TranslateAnswerCommand(qaset.id, qaset.answers[0].id, bm.id, "google", author.id),
    )
    await container.run(
        container.build_translate_variant,
        TranslateVariantCommand(qaset.id, variant.id, bm.id, "google", author.id),
    )

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        loaded = await uow.qasets.get(qaset.id)
    assert loaded is not None
    bm_presence = loaded.presence(bm.id)
    assert bm_presence.answer.text == "bm: Buvez de l'eau."
    assert [v.text for v in bm_presence.variants] == ["bm: Que faire ?"]
    assert [t.other_id for t in loaded.answer_translations(bm_presence.answer.id)] == [
        qaset.answers[0].id
    ]
    assert [t.other_id for t in loaded.variant_translations(variant.id)] == [
        bm_presence.variants[0].id
    ]
    async with migrated_engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM validations")) == 0
