from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

if TYPE_CHECKING:
    from qa_authoring.domain.model.qaset import LanguagePresence, QASet, QuestionVariant


@dataclass(frozen=True, slots=True)
class AnswerResult:
    id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class QuestionVariantResult:
    id: UUID
    language_id: UUID
    text: str

    @classmethod
    def of(cls, variant: QuestionVariant) -> QuestionVariantResult:
        return cls(variant.id, variant.language_id, variant.text)


@dataclass(frozen=True, slots=True)
class LanguagePresenceResult:
    language_id: UUID
    answer: AnswerResult
    variants: tuple[QuestionVariantResult, ...]
    variant_count: int

    @classmethod
    def of(cls, presence: LanguagePresence) -> LanguagePresenceResult:
        return cls(
            presence.language_id,
            AnswerResult(presence.answer.id, presence.answer.text),
            tuple(QuestionVariantResult.of(v) for v in presence.variants),
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
            tuple(LanguagePresenceResult.of(p) for p in qaset.presences()),
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
