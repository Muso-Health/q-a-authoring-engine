from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.qaset_response import (
        LanguagePresenceResult,
        QASetResult,
        QASetSummaryResult,
        QuestionVariantResult,
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


class AnswerResponse(BaseModel):
    id: UUID
    text: str


class QuestionVariantResponse(BaseModel):
    id: UUID
    language_id: UUID
    text: str

    @classmethod
    def of(cls, result: QuestionVariantResult) -> QuestionVariantResponse:
        return cls(id=result.id, language_id=result.language_id, text=result.text)


class LanguagePresenceResponse(BaseModel):
    language_id: UUID
    answer: AnswerResponse
    variants: list[QuestionVariantResponse]
    variant_count: int

    @classmethod
    def of(cls, result: LanguagePresenceResult) -> LanguagePresenceResponse:
        return cls(
            language_id=result.language_id,
            answer=AnswerResponse(id=result.answer.id, text=result.answer.text),
            variants=[QuestionVariantResponse.of(v) for v in result.variants],
            variant_count=result.variant_count,
        )


class QASetResponse(BaseModel):
    id: UUID
    theme_id: UUID
    languages: list[LanguagePresenceResponse]

    @classmethod
    def of(cls, result: QASetResult) -> QASetResponse:
        return cls(
            id=result.id,
            theme_id=result.theme_id,
            languages=[LanguagePresenceResponse.of(p) for p in result.languages],
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
