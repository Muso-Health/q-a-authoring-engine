from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pyarrow.parquet as pq
import pytest

from config.container import Container
from qa_authoring.application.export_errors import NothingToExportError
from qa_authoring.application.export_project_corpus.command import ExportProjectCorpusCommand
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.user import User
from qa_authoring.domain.model.validation import Validation, ValidationState, ValidationSubject
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from qa_authoring.infrastructure.storage.local import LocalBlobStorage
from tests.fakes import AUDIO_POLICY, NOW, FakeAudioProbe, InMemoryAudioStorage

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


def _qaset(theme: Theme, fr: Language, bm: Language) -> QASet:
    """Two languages, three variants, one answer link and one variant link."""
    qaset = QASet.create(theme_id=theme.id, language_id=fr.id, answer_text="Buvez de l'eau.")
    fr_variant = qaset.add_variant(fr.id, "Que boire ?")
    qaset.add_variant(fr.id, "Faut-il boire ?")
    bm_answer = qaset.add_language(bm.id, "Ji min.")
    bm_variant = qaset.add_variant(bm.id, "Mun min?")
    qaset.link_answers(qaset.answers[0].id, bm_answer.id)
    qaset.link_variants(fr_variant.id, bm_variant.id)
    return qaset


async def _seed(engine: AsyncEngine) -> tuple[UUID, set[UUID]]:
    fr = Language.register(LanguageCode("fr"), "French")
    bm = Language.register(LanguageCode("bm"), "Bambara")
    project = Project.create(name="Muso", base_language_id=fr.id)
    protocol = Protocol.create(project_id=project.id, name="Malaria")
    theme = Theme.create(protocol_id=protocol.id, name="Fever")
    reviewer = User.create(email="reviewer@example.org", display_name="Reviewer")
    qasets = [_qaset(theme, fr, bm) for _ in range(4)]
    decisions = [ValidationState.VALIDATED, ValidationState.VALIDATED, ValidationState.REJECTED]
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.languages.add(fr)
        await uow.languages.add(bm)
        await uow.projects.add(project)
        await uow.protocols.add(protocol)
        await uow.themes.add(theme)
        await uow.users.add(reviewer)
        for qaset in qasets:
            await uow.qasets.add(qaset)
        for qaset, decision in zip(qasets, decisions, strict=False):  # the 4th stays undecided
            await uow.validations.add(
                Validation.start(
                    ValidationSubject.for_qaset(qaset.id),
                    decision,
                    actor_user_id=reviewer.id,
                    at=NOW,
                )
            )
    return project.id, {q.id for q in qasets[:2]}


async def test_exports_only_validated_qasets_from_postgres(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    project_id, eligible = await _seed(migrated_engine)
    storage = LocalBlobStorage(tmp_path / "exports", "exports/")
    container = Container(
        partial(SqlAlchemyUnitOfWork, migrated_engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
        clock=lambda: NOW,
        export_storage=storage,
    )

    result = await container.run(
        container.build_export_project_corpus, ExportProjectCorpusCommand(project_id)
    )

    counts = result.counts
    assert (counts.qaset_count, counts.qa_row_count, counts.link_count) == (2, 6, 4)
    rows = pq.read_table(await _path(storage, result.qa_rows.url)).to_pylist()
    links = pq.read_table(await _path(storage, result.translation_links.url)).to_pylist()
    assert {row["qaset_id"] for row in rows} == {str(q) for q in eligible}
    assert {link["qaset_id"] for link in links} == {str(q) for q in eligible}
    assert {row["clinical_validation_state"] for row in rows} == {"validated"}
    assert sorted(row["language_code"] for row in rows) == ["bm", "bm", "fr", "fr", "fr", "fr"]
    assert {
        (link["role"], link["language_a_code"] != link["language_b_code"]) for link in links
    } == {
        ("answer", True),
        ("variant", True),
    }
    keys = [(row["qaset_id"], row["answer_id"], row["question_variant_id"]) for row in rows]
    assert keys == sorted(keys)


async def test_a_project_with_nothing_validated_is_refused(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    fr = Language.register(LanguageCode("fr"), "French")
    project = Project.create(name="Empty", base_language_id=fr.id)
    async with SqlAlchemyUnitOfWork(migrated_engine) as uow:
        await uow.languages.add(fr)
        await uow.projects.add(project)
    container = Container(
        partial(SqlAlchemyUnitOfWork, migrated_engine),
        audio_storage=InMemoryAudioStorage(),
        audio_probe=FakeAudioProbe(),
        audio_policy=AUDIO_POLICY,
        export_storage=LocalBlobStorage(tmp_path, "exports/"),
    )
    with pytest.raises(NothingToExportError):
        await container.run(
            container.build_export_project_corpus, ExportProjectCorpusCommand(project.id)
        )


async def _path(storage: LocalBlobStorage, url: str) -> str:
    """The local adapter's "signed" URL is the file URI itself."""
    assert await storage.read(url)
    return url.removeprefix("file://")
