from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.schemas.audio import AudioSummaryResponse

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.qaset_response import (
        AttachedCategoryResult,
        AttachedIntentResult,
        LanguagePresenceResult,
        QASetResult,
        QASetSummaryResult,
        QuestionVariantResult,
        TranslationLinkResult,
        TranslationResult,
    )

# Text blankness is a domain rule (422 invalid_text); unknown fields are rejected here.


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnswerInLanguageRequest(_Strict):
    """Create a QA set, or add a language to one, with the answer in that language."""

    language_id: UUID
    answer_text: str


class TextRequest(_Strict):
    text: str


class LinkAnswersRequest(_Strict):
    answer_a_id: UUID
    answer_b_id: UUID


class LinkVariantsRequest(_Strict):
    variant_a_id: UUID
    variant_b_id: UUID


class AnswerLinkResponse(BaseModel):
    """``answer_ids`` is the canonical pair: the smaller id first, whatever the request order."""

    id: UUID
    answer_ids: tuple[UUID, UUID]

    @classmethod
    def of(cls, result: TranslationLinkResult) -> AnswerLinkResponse:
        return cls(id=result.id, answer_ids=result.item_ids)


class VariantLinkResponse(BaseModel):
    """``variant_ids`` is the canonical pair: the smaller id first, whatever the request order."""

    id: UUID
    variant_ids: tuple[UUID, UUID]

    @classmethod
    def of(cls, result: TranslationLinkResult) -> VariantLinkResponse:
        return cls(id=result.id, variant_ids=result.item_ids)


class TranslationResponse(BaseModel):
    """One translation link, seen from the item that carries it."""

    link_id: UUID
    other_id: UUID
    other_language_id: UUID

    @classmethod
    def of(cls, result: TranslationResult) -> TranslationResponse:
        return cls(
            link_id=result.link_id,
            other_id=result.other_id,
            other_language_id=result.other_language_id,
        )


class AttachedIntentResponse(BaseModel):
    intent_id: UUID
    text: str

    @classmethod
    def of(cls, result: AttachedIntentResult) -> AttachedIntentResponse:
        return cls(intent_id=result.intent_id, text=result.text)


class AttachIntentRequest(_Strict):
    intent_id: UUID


class AddCategoryRequest(_Strict):
    category_id: UUID


class AttachedCategoryResponse(BaseModel):
    category_id: UUID
    name: str

    @classmethod
    def of(cls, result: AttachedCategoryResult) -> AttachedCategoryResponse:
        return cls(category_id=result.category_id, name=result.name)


class AnswerResponse(BaseModel):
    id: UUID
    text: str
    links: list[TranslationResponse]
    audio: AudioSummaryResponse | None


class QuestionVariantResponse(BaseModel):
    id: UUID
    language_id: UUID
    text: str
    links: list[TranslationResponse]
    intents: list[AttachedIntentResponse]
    audio: AudioSummaryResponse | None

    @classmethod
    def of(cls, result: QuestionVariantResult) -> QuestionVariantResponse:
        return cls(
            id=result.id,
            language_id=result.language_id,
            text=result.text,
            links=[TranslationResponse.of(link) for link in result.links],
            intents=[AttachedIntentResponse.of(intent) for intent in result.intents],
            audio=AudioSummaryResponse.of(result.audio),
        )


class LanguagePresenceResponse(BaseModel):
    language_id: UUID
    answer: AnswerResponse
    variants: list[QuestionVariantResponse]
    variant_count: int

    @classmethod
    def of(cls, result: LanguagePresenceResult) -> LanguagePresenceResponse:
        return cls(
            language_id=result.language_id,
            answer=AnswerResponse(
                id=result.answer.id,
                text=result.answer.text,
                links=[TranslationResponse.of(link) for link in result.answer.links],
                audio=AudioSummaryResponse.of(result.answer.audio),
            ),
            variants=[QuestionVariantResponse.of(v) for v in result.variants],
            variant_count=result.variant_count,
        )


class QASetResponse(BaseModel):
    id: UUID
    theme_id: UUID
    languages: list[LanguagePresenceResponse]
    categories: list[AttachedCategoryResponse]

    @classmethod
    def of(cls, result: QASetResult) -> QASetResponse:
        return cls(
            id=result.id,
            theme_id=result.theme_id,
            languages=[LanguagePresenceResponse.of(p) for p in result.languages],
            categories=[AttachedCategoryResponse.of(c) for c in result.categories],
        )


class LanguageSummaryResponse(BaseModel):
    language_id: UUID
    variant_count: int


class QASetSummaryResponse(BaseModel):
    id: UUID
    theme_id: UUID
    languages: list[LanguageSummaryResponse]


class QASetsResponse(BaseModel):
    items: list[QASetSummaryResponse]

    @classmethod
    def of(cls, results: Sequence[QASetSummaryResult]) -> QASetsResponse:
        return cls(
            items=[
                QASetSummaryResponse(
                    id=r.id,
                    theme_id=r.theme_id,
                    languages=[
                        LanguageSummaryResponse(
                            language_id=s.language_id, variant_count=s.variant_count
                        )
                        for s in r.languages
                    ],
                )
                for r in results
            ]
        )
