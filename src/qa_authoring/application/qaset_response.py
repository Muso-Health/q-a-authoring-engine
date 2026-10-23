from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

if TYPE_CHECKING:
    from qa_authoring.domain.model.qaset import (
        LanguagePresence,
        QASet,
        QuestionVariant,
        Translation,
        TranslationLink,
    )


@dataclass(frozen=True, slots=True)
class TranslationResult:
    link_id: UUID
    other_id: UUID
    other_language_id: UUID

    @classmethod
    def of(cls, translation: Translation) -> TranslationResult:
        return cls(translation.link_id, translation.other_id, translation.other_language_id)


@dataclass(frozen=True, slots=True)
class TranslationLinkResult:
    id: UUID
    item_ids: tuple[UUID, UUID]

    @classmethod
    def of(cls, link: TranslationLink) -> TranslationLinkResult:
        return cls(link.id, (link.low_id, link.high_id))


@dataclass(frozen=True, slots=True)
class AnswerResult:
    id: UUID
    text: str
    links: tuple[TranslationResult, ...]


@dataclass(frozen=True, slots=True)
class QuestionVariantResult:
    id: UUID
    language_id: UUID
    text: str
    links: tuple[TranslationResult, ...]

    @classmethod
    def of(cls, qaset: QASet, variant: QuestionVariant) -> QuestionVariantResult:
        links = tuple(TranslationResult.of(t) for t in qaset.variant_translations(variant.id))
        return cls(variant.id, variant.language_id, variant.text, links)


@dataclass(frozen=True, slots=True)
class LanguagePresenceResult:
    language_id: UUID
    answer: AnswerResult
    variants: tuple[QuestionVariantResult, ...]
    variant_count: int

    @classmethod
    def of(cls, qaset: QASet, presence: LanguagePresence) -> LanguagePresenceResult:
        answer = presence.answer
        links = tuple(TranslationResult.of(t) for t in qaset.answer_translations(answer.id))
        return cls(
            presence.language_id,
            AnswerResult(answer.id, answer.text, links),
            tuple(QuestionVariantResult.of(qaset, v) for v in presence.variants),
            presence.variant_count,
        )


@dataclass(frozen=True, slots=True)
class QASetResult:
    id: UUID
    theme_id: UUID
    languages: tuple[LanguagePresenceResult, ...]

    @classmethod
    def of(cls, qaset: QASet) -> QASetResult:
        return cls(
            qaset.id,
            qaset.theme_id,
            tuple(LanguagePresenceResult.of(qaset, p) for p in qaset.presences()),
        )


@dataclass(frozen=True, slots=True)
class LanguageSummaryResult:
    language_id: UUID
    variant_count: int


@dataclass(frozen=True, slots=True)
class QASetSummaryResult:
    id: UUID
    theme_id: UUID
    languages: tuple[LanguageSummaryResult, ...]

    @classmethod
    def of(cls, qaset: QASet) -> QASetSummaryResult:
        return cls(
            qaset.id,
            qaset.theme_id,
            tuple(LanguageSummaryResult(p.language_id, p.variant_count) for p in qaset.presences()),
        )
