from __future__ import annotations

import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from qa_authoring.application.corpus_datasets import CorpusDatasets, QaRow
from qa_authoring.application.export_errors import NothingToExportError
from qa_authoring.application.export_project_corpus.command import ExportProjectCorpusCommand
from qa_authoring.application.export_project_corpus.handler import ExportProjectCorpusHandler
from qa_authoring.application.project_errors import ProjectNotFoundError
from qa_authoring.domain.model.category import Category
from qa_authoring.domain.model.intent import Intent
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.project import Project
from qa_authoring.domain.model.protocol import Protocol
from qa_authoring.domain.model.qaset import AudioReference, QASet
from qa_authoring.domain.model.theme import Theme
from qa_authoring.domain.model.validation import Validation, ValidationState, ValidationSubject
from qa_authoring.domain.value_objects.language_code import LanguageCode
from tests.fakes import NOW, FakeExporter, InMemoryBlobStorage, InMemoryStore

TTL = 600
VALIDATED, REJECTED = ValidationState.VALIDATED, ValidationState.REJECTED


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


class World:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.fr = self._language("fr", "French")
        self.bm = self._language("bm", "Bambara")
        self.project = Project.create(name="Muso", base_language_id=self.fr)
        self.protocol = Protocol.create(project_id=self.project.id, name="Malaria protocol")
        self.theme = Theme.create(protocol_id=self.protocol.id, name="Fever")
        self.store.projects.rows[self.project.id] = self.project
        self.store.protocols.rows[self.protocol.id] = self.protocol
        self.store.themes.rows[self.theme.id] = self.theme
        self.storage = InMemoryBlobStorage("exports")
        self.exporter = FakeExporter()
        self.handler = ExportProjectCorpusHandler(
            self.store.projects,
            self.store.protocols,
            self.store.themes,
            self.store.qasets,
            self.store.languages,
            self.store.intents,
            self.store.categories,
            self.store.validations,
            self.exporter,
            self.storage,
            TTL,
            lambda: NOW,
        )

    def _language(self, code: str, name: str) -> UUID:
        language = Language.register(LanguageCode(code), name)
        self.store.languages.rows[language.id] = language
        return language.id

    def qaset(
        self, clinical: ValidationState | None = VALIDATED, theme: Theme | None = None
    ) -> QASet:
        qaset = QASet.create(
            theme_id=(theme or self.theme).id, language_id=self.fr, answer_text="Buvez de l'eau."
        )
        qaset.add_variant(self.fr, "Que boire ?")
        self.store.qasets.rows[qaset.id] = qaset
        if clinical is not None:
            self.decide(ValidationSubject.for_qaset(qaset.id), clinical)
        return qaset

    def decide(self, subject: ValidationSubject, *states: ValidationState) -> None:
        first, *others = states
        validation = Validation.start(subject, first, actor_user_id=uuid4(), at=NOW)
        for state in others:
            validation.decide(state, actor_user_id=uuid4(), at=NOW)
        self.store.validations.rows[subject] = validation

    def reset(self, subject: ValidationSubject) -> None:
        self.store.validations.rows[subject].reset(actor_user_id=uuid4(), at=NOW)

    async def export(self, project_id: UUID | None = None) -> CorpusDatasets:
        await self.handler(ExportProjectCorpusCommand(project_id or self.project.id))
        [datasets] = self.exporter.calls
        return datasets


@pytest.fixture
def world() -> World:
    return World()


async def test_only_clinically_validated_qasets_are_exported(world: World) -> None:
    validated = world.qaset(VALIDATED)
    world.qaset(REJECTED)
    world.qaset(clinical=None)
    reset = world.qaset(VALIDATED)
    world.reset(ValidationSubject.for_qaset(reset.id))
    revalidated = world.qaset(REJECTED)
    world.decide(ValidationSubject.for_qaset(revalidated.id), REJECTED, VALIDATED)

    datasets = await world.export()

    assert {row.qaset_id for row in datasets.qa_rows} == {validated.id, revalidated.id}
    assert {row.clinical_validation_state for row in datasets.qa_rows} == {"validated"}


async def test_a_row_per_variant_carries_its_catalog_and_qaset_context(world: World) -> None:
    qaset = world.qaset()
    malaria, fever = Category.register("Malaria"), Category.register("Fever")
    dosage, children = Intent.register("Dosage"), Intent.register("Children")
    for item in (malaria, fever):
        world.store.categories.rows[item.id] = item
        qaset.add_category(item.id)
    for intent in (dosage, children):
        world.store.intents.rows[intent.id] = intent
        qaset.attach_intent(qaset.variants[0].id, intent.id)

    [row] = (await world.export()).qa_rows

    answer, variant = qaset.answers[0], qaset.variants[0]
    assert row == QaRow(
        project_id=world.project.id,
        project_name="Muso",
        base_language_code="fr",
        protocol_id=world.protocol.id,
        protocol_name="Malaria protocol",
        theme_id=world.theme.id,
        theme_name="Fever",
        qaset_id=qaset.id,
        category_names=("Fever", "Malaria"),
        language_code="fr",
        question_variant_id=variant.id,
        question_text="Que boire ?",
        answer_id=answer.id,
        answer_text="Buvez de l'eau.",
        intents=("Children", "Dosage"),
        variant_audio_uri=None,
        answer_audio_uri=None,
        clinical_validation_state="validated",
        translation_validation_state=None,
        variant_audio_validation_state=None,
        answer_audio_validation_state=None,
    )


async def test_every_language_is_exported_and_other_states_never_exclude(world: World) -> None:
    qaset = world.qaset()
    bm_answer = qaset.add_language(world.bm, "Ji min.")
    rejected = qaset.add_variant(world.bm, "Mun min?")
    undecided = qaset.add_variant(world.bm, "Ji min wa?")
    world.decide(ValidationSubject.for_variant(rejected.id), REJECTED)
    world.decide(ValidationSubject.for_answer(bm_answer.id), REJECTED)

    rows = {row.question_variant_id: row for row in (await world.export()).qa_rows}

    assert {row.language_code for row in rows.values()} == {"fr", "bm"}
    assert rows[rejected.id].translation_validation_state == "rejected"
    assert rows[undecided.id].translation_validation_state == "pending"
    assert rows[rejected.id].answer_id == bm_answer.id
    assert rows[qaset.variants[0].id].translation_validation_state is None  # the base language


async def test_audio_uris_and_states_are_carried_where_present(world: World) -> None:
    qaset = world.qaset()
    answer_audio, variant_audio = _audio("answer"), _audio("variant")
    qaset.set_answer_audio(qaset.answers[0].id, answer_audio)
    qaset.set_variant_audio(qaset.variants[0].id, variant_audio)
    silent = qaset.add_variant(world.fr, "Faut-il boire ?")
    world.decide(ValidationSubject.for_audio(variant_audio.id), REJECTED)

    rows = {row.question_variant_id: row for row in (await world.export()).qa_rows}

    recorded = rows[qaset.variants[0].id]
    assert (recorded.variant_audio_uri, recorded.answer_audio_uri) == (
        "memory://audio/variant",
        "memory://audio/answer",
    )
    assert recorded.variant_audio_validation_state == "rejected"
    assert recorded.answer_audio_validation_state == "pending"
    assert rows[silent.id].variant_audio_uri is None
    assert rows[silent.id].variant_audio_validation_state is None
    assert rows[silent.id].answer_audio_uri == "memory://audio/answer"


async def test_a_language_without_variants_contributes_no_row(world: World) -> None:
    qaset = world.qaset()
    qaset.add_language(world.bm, "Ji min.")
    rows = (await world.export()).qa_rows
    assert [row.language_code for row in rows] == ["fr"]


async def test_translation_links_of_eligible_qasets_only(world: World) -> None:
    eligible, other = world.qaset(), world.qaset(REJECTED)
    for qaset in (eligible, other):
        bm_answer = qaset.add_language(world.bm, "Ji min.")
        bm_variant = qaset.add_variant(world.bm, "Mun min?")
        qaset.link_answers(qaset.answers[0].id, bm_answer.id)
        qaset.link_variants(qaset.variants[0].id, bm_variant.id)

    links = (await world.export()).translation_links

    assert {link.qaset_id for link in links} == {eligible.id}
    assert [link.role for link in links] == ["answer", "variant"]
    for link, stored in zip(links, (*eligible.answer_links, *eligible.variant_links), strict=True):
        assert (link.item_a_id, link.item_b_id) == (stored.low_id, stored.high_id)
        languages = {
            item.id: "fr" if item.language_id == world.fr else "bm"
            for item in (*eligible.answers, *eligible.variants)
        }
        assert (link.language_a_code, link.language_b_code) == (
            languages[stored.low_id],
            languages[stored.high_id],
        )


async def test_rows_are_ordered_by_ids_across_protocols_and_themes(world: World) -> None:
    second_theme = Theme.create(protocol_id=world.protocol.id, name="Another")
    world.store.themes.rows[second_theme.id] = second_theme
    qasets = [world.qaset(), world.qaset(theme=second_theme), world.qaset()]
    for qaset in qasets:
        qaset.add_variant(world.fr, "Encore ?")
        bm = qaset.add_language(world.bm, "Ji.")
        qaset.link_answers(qaset.answers[0].id, bm.id)
        qaset.link_variants(qaset.variants[0].id, qaset.add_variant(world.bm, "Ji?").id)

    datasets = await world.export()

    keys = [(r.qaset_id, r.answer_id, r.question_variant_id) for r in datasets.qa_rows]
    assert keys == sorted(keys) and len(keys) == 9
    link_keys = [(link.qaset_id, link.role, link.item_a_id) for link in datasets.translation_links]
    assert link_keys == sorted(link_keys) and len(link_keys) == 6


async def test_returns_short_lived_urls_and_counts(world: World) -> None:
    qaset = world.qaset()
    qaset.add_variant(world.fr, "Encore ?")
    qaset.link_answers(qaset.answers[0].id, qaset.add_language(world.bm, "Ji.").id)

    result = await world.handler(ExportProjectCorpusCommand(world.project.id))

    expires = NOW + timedelta(seconds=TTL)
    assert result.qa_rows.url == f"https://signed.example/exports/qa_rows?ttl={TTL}"
    assert result.translation_links.url == (
        f"https://signed.example/exports/translation_links?ttl={TTL}"
    )
    assert result.qa_rows.expires_at == result.translation_links.expires_at == expires
    assert (result.counts.qaset_count, result.counts.qa_row_count, result.counts.link_count) == (
        1,
        2,
        1,
    )


@pytest.mark.parametrize("clinical", [None, REJECTED])
async def test_nothing_eligible_is_a_conflict(
    world: World, clinical: ValidationState | None
) -> None:
    world.qaset(clinical)
    with pytest.raises(NothingToExportError):
        await world.handler(ExportProjectCorpusCommand(world.project.id))
    assert world.exporter.calls == []


async def test_a_project_without_qasets_has_nothing_to_export(world: World) -> None:
    with pytest.raises(NothingToExportError):
        await world.handler(ExportProjectCorpusCommand(world.project.id))


async def test_unknown_project(world: World) -> None:
    with pytest.raises(ProjectNotFoundError):
        await world.handler(ExportProjectCorpusCommand(uuid4()))


async def test_other_projects_are_not_exported(world: World) -> None:
    other = Project.create(name="Other", base_language_id=world.fr)
    protocol = Protocol.create(project_id=other.id, name="Pr")
    theme = Theme.create(protocol_id=protocol.id, name="T")
    world.store.projects.rows[other.id] = other
    world.store.protocols.rows[protocol.id] = protocol
    world.store.themes.rows[theme.id] = theme
    mine, _ = world.qaset(), world.qaset(theme=theme)

    rows = (await world.export()).qa_rows

    assert {row.qaset_id for row in rows} == {mine.id}


async def test_nothing_is_written(world: World) -> None:
    world.qaset()
    before = dict(world.store.validations.rows)
    await world.export()
    assert world.store.events == []
    assert world.store.validations.rows == before
