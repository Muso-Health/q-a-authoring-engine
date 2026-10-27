from __future__ import annotations

import itertools
from functools import partial
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from config.container import Container
from qa_authoring.application.author_qa_pairs.command import AuthorQAPairsCommand, QAPair
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import AUDIO_POLICY, FakeAudioProbe, InMemoryAudioStorage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def _world(engine: AsyncEngine) -> tuple[Container, Theme, Language]:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="Muso", base_language_id=bm.id)
    protocol = Protocol.create(project_id=project.id, name="Malaria")
    theme = Theme.create(protocol_id=protocol.id, name="Fever")
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.languages.add(bm)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
    container = Container(
        partial(SqlAlchemyUnitOfWork, engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
    )
    return container, theme, bm


async def test_a_batch_keeps_its_insertion_order_and_merges_on_the_answer(
    migrated_engine: AsyncEngine,
) -> None:
    container, theme, bm = await _world(migrated_engine)
    existing = QASet.create(theme_id=theme.id, language_id=bm.id, answer_text="A")
    existing.add_variant(bm.id, "Q-existing")
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.qasets.add(existing)

    questions = [f"Q{n:02d}" for n in range(40)]
    pairs = (*(QAPair(q, " A ") for q in questions), QAPair("Q-existing", "A"), QAPair("X", "B"))
    result = await container.run(
        container.build_author_qa_pairs, AuthorQAPairsCommand(theme.id, pairs)
    )

    assert (result.qasets_created, result.qasets_updated, result.variants_added) == (1, 1, 41)
    assert result.skipped_rows == (40,)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        stored = {
            q.presence(bm.id).answer.text: q for q in await uow.qasets.list_by_theme(theme.id)
        }
    assert sorted(stored) == ["A", "B"]
    assert stored["A"].id == existing.id
    assert [v.text for v in stored["A"].variants] == ["Q-existing", *questions]
    assert [v.text for v in stored["B"].variants] == ["X"]

    # Inserted in one transaction, the variants still get strictly increasing timestamps.
    async with migrated_engine.connect() as connection:
        stamps = (
            await connection.scalars(
                text(
                    "SELECT created_at FROM question_variants WHERE qaset_id = :id "
                    "ORDER BY created_at"
                ),
                {"id": existing.id},
            )
        ).all()
    assert len(stamps) == 41
    assert all(earlier < later for earlier, later in itertools.pairwise(stamps[1:]))
