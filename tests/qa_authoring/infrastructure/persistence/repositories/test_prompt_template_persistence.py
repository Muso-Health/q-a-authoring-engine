from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

import pytest

from config.container import Container
from qa_authoring.application.seed_prompt_templates.command import SeedPromptTemplatesCommand
from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    PromptTemplate,
    PromptTemplateKey,
)
from qa_authoring.domain.model.user import User
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import AUDIO_POLICY, NOW, FakeAudioProbe, InMemoryAudioStorage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

T1 = datetime(2026, 10, 25, 8, 30, tzinfo=UTC)
TRANSLATION = "Translate {text} from {source_language} into {target_language}."


def _container(engine: AsyncEngine) -> Container:
    return Container(
        partial(SqlAlchemyUnitOfWork, engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
        clock=lambda: NOW,
    )


async def test_seeded_defaults_are_idempotent(migrated_engine: AsyncEngine) -> None:
    container = _container(migrated_engine)
    for _ in range(2):
        await container.run(container.build_seed_prompt_templates, SeedPromptTemplatesCommand())

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        templates = await uow.prompt_templates.list()

    assert [(t.key, t.content, t.updated_by, t.updated_at) for t in templates] == [
        (key, DEFAULT_TEMPLATES[key], None, NOW) for key in PromptTemplateKey
    ]


async def test_template_round_trip(migrated_engine: AsyncEngine) -> None:
    editor = User.create(email="editor@example.org", display_name="Editor")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.users.add(editor)
        await uow.prompt_templates.add(
            PromptTemplate.create(
                PromptTemplateKey.TRANSLATION,
                DEFAULT_TEMPLATES[PromptTemplateKey.TRANSLATION],
                updated_by=None,
                at=NOW,
            )
        )

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        template = await uow.prompt_templates.get(PromptTemplateKey.TRANSLATION)
        assert template is not None
        template.revise(TRANSLATION, updated_by=editor.id, at=T1)
        await uow.prompt_templates.update(template)

    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        reloaded = await uow.prompt_templates.get(PromptTemplateKey.TRANSLATION)
        missing = await uow.prompt_templates.get(PromptTemplateKey.VARIANT_GENERATION)

    assert reloaded is not None
    assert (reloaded.content, reloaded.updated_by, reloaded.updated_at) == (
        TRANSLATION,
        editor.id,
        T1,
    )
    assert missing is None
