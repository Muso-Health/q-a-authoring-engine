from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.schemas.qasets import (
    AnswerLinkResponse,
    LanguagePresenceResponse,
    QuestionVariantResponse,
    VariantLinkResponse,
)

if TYPE_CHECKING:
    from qa_authoring.application.translation_response import (
        TranslatedAnswerResult,
        TranslatedVariantResult,
    )


class TranslateRequest(BaseModel):
    """``engine`` is ``llm`` or ``google`` (422 ``unknown_engine`` otherwise)."""

    model_config = ConfigDict(extra="forbid")

    target_language_id: UUID
    engine: str


class TranslatedAnswerResponse(BaseModel):
    presence: LanguagePresenceResponse
    link: AnswerLinkResponse

    @classmethod
    def of(cls, result: TranslatedAnswerResult) -> TranslatedAnswerResponse:
        return cls(
            presence=LanguagePresenceResponse.of(result.presence),
            link=AnswerLinkResponse.of(result.link),
        )


class TranslatedVariantResponse(BaseModel):
    variant: QuestionVariantResponse
    link: VariantLinkResponse

    @classmethod
    def of(cls, result: TranslatedVariantResult) -> TranslatedVariantResponse:
        return cls(
            variant=QuestionVariantResponse.of(result.variant),
            link=VariantLinkResponse.of(result.link),
        )
