from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from qa_authoring.application.corpus_datasets import CorpusDatasets, QaRow, TranslationLinkRow
from qa_authoring.application.documentation_response import DownloadUrlResult
from qa_authoring.application.export_errors import NothingToExportError
from qa_authoring.application.export_response import ExportCounts, ExportResult
from qa_authoring.application.project_errors import ProjectNotFoundError
from qa_authoring.domain.model.validation import ValidationState, ValidationSubject

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime
    from uuid import UUID

    from qa_authoring.application.export_project_corpus.command import (
        ExportProjectCorpusCommand,
    )
    from qa_authoring.application.ports.category_repository import CategoryRepository
    from qa_authoring.application.ports.corpus_export import ExportPort
    from qa_authoring.application.ports.export_storage import ExportStoragePort
    from qa_authoring.application.ports.intent_repository import IntentRepository
    from qa_authoring.application.ports.language_repository import LanguageRepository
    from qa_authoring.application.ports.project_repository import ProjectRepository
    from qa_authoring.application.ports.protocol_repository import ProtocolRepository
    from qa_authoring.application.ports.qaset_repository import QASetRepository
    from qa_authoring.application.ports.theme_repository import ThemeRepository
    from qa_authoring.application.ports.validation_repository import ValidationRepository
    from qa_authoring.domain.model.project import Project
    from qa_authoring.domain.model.protocol import Protocol
    from qa_authoring.domain.model.qaset import Answer, AudioReference, QASet, QuestionVariant
    from qa_authoring.domain.model.theme import Theme


class ExportProjectCorpusHandler:
    """Exports a project's publishable corpus: the QA sets whose clinical validation is
    ``validated``, in every language. Translation and audio validation states are carried for
    traceability and never exclude anything. Read-only."""

    def __init__(
        self,
        projects: ProjectRepository,
        protocols: ProtocolRepository,
        themes: ThemeRepository,
        qasets: QASetRepository,
        languages: LanguageRepository,
        intents: IntentRepository,
        categories: CategoryRepository,
        validations: ValidationRepository,
        exporter: ExportPort,
        storage: ExportStoragePort,
        download_url_ttl_seconds: int,
        clock: Callable[[], datetime],
    ) -> None:
        self._projects = projects
        self._protocols = protocols
        self._themes = themes
        self._qasets = qasets
        self._languages = languages
        self._intents = intents
        self._categories = categories
        self._validations = validations
        self._exporter = exporter
        self._storage = storage
        self._ttl = download_url_ttl_seconds
        self._clock = clock

    async def __call__(self, command: ExportProjectCorpusCommand) -> ExportResult:
        project = await self._projects.get(command.project_id)
        if project is None:
            raise ProjectNotFoundError(command.project_id)
        eligible = await self._eligible(project)
        if not eligible:
            raise NothingToExportError(project.id)
        datasets = await self._datasets(project, eligible)
        artifacts = await self._exporter.export(datasets)
        expires_at = self._clock() + timedelta(seconds=self._ttl)
        return ExportResult(
            qa_rows=DownloadUrlResult(
                await self._storage.signed_url(artifacts.qa_rows, self._ttl), expires_at
            ),
            translation_links=DownloadUrlResult(
                await self._storage.signed_url(artifacts.translation_links, self._ttl), expires_at
            ),
            counts=ExportCounts(
                qaset_count=len(eligible),
                qa_row_count=len(datasets.qa_rows),
                link_count=len(datasets.translation_links),
            ),
        )

    async def _eligible(self, project: Project) -> list[tuple[Protocol, Theme, QASet]]:
        candidates = [
            (protocol, theme, qaset)
            for protocol in await self._protocols.list_by_project(project.id)
            for theme in await self._themes.list_by_protocol(protocol.id)
            for qaset in await self._qasets.list_by_theme(theme.id)
        ]
        clinical = await self._validations.current_states(
            {ValidationSubject.for_qaset(qaset.id) for _, _, qaset in candidates}
        )
        return [
            candidate
            for candidate in candidates
            if clinical.get(ValidationSubject.for_qaset(candidate[2].id))
            is ValidationState.VALIDATED
        ]

    async def _datasets(
        self, project: Project, eligible: list[tuple[Protocol, Theme, QASet]]
    ) -> CorpusDatasets:
        qasets = [qaset for _, _, qaset in eligible]
        codes = {language.id: language.code.value for language in await self._languages.list()}
        intent_ids = {i for qaset in qasets for v in qaset.variants for i in v.intent_ids}
        category_ids = {c for qaset in qasets for c in qaset.category_ids}
        intents = await self._intents.get_many(intent_ids) if intent_ids else {}
        categories = await self._categories.get_many(category_ids) if category_ids else {}
        states = await self._validations.current_states(
            {
                subject
                for qaset in qasets
                for subject in (
                    *(ValidationSubject.for_answer(a.id) for a in qaset.answers),
                    *(ValidationSubject.for_variant(v.id) for v in qaset.variants),
                    *(ValidationSubject.for_audio(a.id) for a in qaset.audios),
                )
            }
        )

        def state(subject: ValidationSubject) -> str:
            return states.get(subject, ValidationState.PENDING).value

        def audio_state(audio: AudioReference | None) -> str | None:
            return None if audio is None else state(ValidationSubject.for_audio(audio.id))

        def row(
            protocol: Protocol, theme: Theme, qaset: QASet, answer: Answer, variant: QuestionVariant
        ) -> QaRow:
            in_base = variant.language_id == project.base_language_id
            return QaRow(
                project_id=project.id,
                project_name=project.name,
                base_language_code=codes[project.base_language_id],
                protocol_id=protocol.id,
                protocol_name=protocol.name,
                theme_id=theme.id,
                theme_name=theme.name,
                qaset_id=qaset.id,
                category_names=tuple(sorted(categories[c].name for c in qaset.category_ids)),
                language_code=codes[variant.language_id],
                question_variant_id=variant.id,
                question_text=variant.text,
                answer_id=answer.id,
                answer_text=answer.text,
                intents=tuple(sorted(intents[i].text for i in variant.intent_ids)),
                variant_audio_uri=_uri(variant.audio),
                answer_audio_uri=_uri(answer.audio),
                clinical_validation_state=ValidationState.VALIDATED.value,
                translation_validation_state=(
                    None if in_base else state(ValidationSubject.for_variant(variant.id))
                ),
                variant_audio_validation_state=audio_state(variant.audio),
                answer_audio_validation_state=audio_state(answer.audio),
            )

        qa_rows = [
            row(protocol, theme, qaset, presence.answer, variant)
            for protocol, theme, qaset in eligible
            for presence in qaset.presences()
            for variant in presence.variants
        ]
        links = [link for qaset in qasets for link in _links(qaset, codes)]
        qa_rows.sort(key=lambda r: (r.qaset_id, r.answer_id, r.question_variant_id))
        links.sort(key=lambda link: (link.qaset_id, link.role, link.item_a_id, link.item_b_id))
        return CorpusDatasets(tuple(qa_rows), tuple(links))


def _uri(audio: AudioReference | None) -> str | None:
    return None if audio is None else audio.storage_uri


def _links(qaset: QASet, codes: Mapping[UUID, str]) -> list[TranslationLinkRow]:
    answers = {a.id: a.language_id for a in qaset.answers}
    variants = {v.id: v.language_id for v in qaset.variants}
    return [
        *(
            TranslationLinkRow(
                "answer",
                link.low_id,
                link.high_id,
                qaset.id,
                codes[answers[link.low_id]],
                codes[answers[link.high_id]],
            )
            for link in qaset.answer_links
        ),
        *(
            TranslationLinkRow(
                "variant",
                link.low_id,
                link.high_id,
                qaset.id,
                codes[variants[link.low_id]],
                codes[variants[link.high_id]],
            )
            for link in qaset.variant_links
        ),
    ]
