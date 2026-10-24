from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

from qa_authoring.domain.model.validation import ValidationState, ValidationSubject

if TYPE_CHECKING:
    from collections.abc import Mapping

    from qa_authoring.domain.model.qaset import (
        AudioReference,
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
class QASetLookups:
    """What a QA set view needs from outside the aggregate: catalogue texts for its attached
    intents and categories, and the current validation state of the set and its items."""

    intent_texts: Mapping[UUID, str] = field(default_factory=dict)
    category_names: Mapping[UUID, str] = field(default_factory=dict)
    validation_states: Mapping[ValidationSubject, ValidationState] = field(default_factory=dict)

    def state_of(self, subject: ValidationSubject) -> ValidationState | None:
        """The decided state, or None while pending (never decided, or reset)."""
        state = self.validation_states.get(subject)
        return None if state is ValidationState.PENDING else state


NO_LOOKUPS = QASetLookups()


@dataclass(frozen=True, slots=True)
class AudioSummaryResult:
    audio_id: UUID
    mime_type: str
    duration_ms: int
    size_bytes: int
    checksum_sha256: str
    audio_validation: ValidationState | None

    @classmethod
    def of(cls, audio: AudioReference | None, lookups: QASetLookups) -> AudioSummaryResult | None:
        if audio is None:
            return None
        return cls(
            audio.id,
            audio.mime_type,
            audio.duration_ms,
            audio.size_bytes,
            audio.checksum_sha256,
            lookups.state_of(ValidationSubject.for_audio(audio.id)),
        )


@dataclass(frozen=True, slots=True)
class AttachedCategoryResult:
    category_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class AttachedIntentResult:
    intent_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class AnswerResult:
    id: UUID
    text: str
    links: tuple[TranslationResult, ...]
    audio: AudioSummaryResult | None
    translation_validation: ValidationState | None


@dataclass(frozen=True, slots=True)
class QuestionVariantResult:
    id: UUID
    language_id: UUID
    text: str
    links: tuple[TranslationResult, ...]
    intents: tuple[AttachedIntentResult, ...]
    audio: AudioSummaryResult | None
    translation_validation: ValidationState | None

    @classmethod
    def of(
        cls, qaset: QASet, variant: QuestionVariant, lookups: QASetLookups
    ) -> QuestionVariantResult:
        links = tuple(TranslationResult.of(t) for t in qaset.variant_translations(variant.id))
        intents = tuple(
            AttachedIntentResult(i, lookups.intent_texts[i]) for i in variant.intent_ids
        )
        return cls(
            variant.id,
            variant.language_id,
            variant.text,
            links,
            intents,
            AudioSummaryResult.of(variant.audio, lookups),
            lookups.state_of(ValidationSubject.for_variant(variant.id)),
        )


@dataclass(frozen=True, slots=True)
class LanguagePresenceResult:
    language_id: UUID
    answer: AnswerResult
    variants: tuple[QuestionVariantResult, ...]
    variant_count: int

    @classmethod
    def of(
        cls, qaset: QASet, presence: LanguagePresence, lookups: QASetLookups
    ) -> LanguagePresenceResult:
        answer = presence.answer
        links = tuple(TranslationResult.of(t) for t in qaset.answer_translations(answer.id))
        return cls(
            presence.language_id,
            AnswerResult(
                answer.id,
                answer.text,
                links,
                AudioSummaryResult.of(answer.audio, lookups),
                lookups.state_of(ValidationSubject.for_answer(answer.id)),
            ),
            tuple(QuestionVariantResult.of(qaset, v, lookups) for v in presence.variants),
            presence.variant_count,
        )


@dataclass(frozen=True, slots=True)
class QASetResult:
    id: UUID
    theme_id: UUID
    languages: tuple[LanguagePresenceResult, ...]
    categories: tuple[AttachedCategoryResult, ...]
    clinical_validation: ValidationState | None

    @classmethod
    def of(cls, qaset: QASet, lookups: QASetLookups) -> QASetResult:
        return cls(
            qaset.id,
            qaset.theme_id,
            tuple(LanguagePresenceResult.of(qaset, p, lookups) for p in qaset.presences()),
            tuple(AttachedCategoryResult(c, lookups.category_names[c]) for c in qaset.category_ids),
            lookups.state_of(ValidationSubject.for_qaset(qaset.id)),
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
