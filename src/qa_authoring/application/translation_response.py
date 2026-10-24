from __future__ import annotations

from dataclasses import dataclass

from qa_authoring.application.qaset_response import (  # noqa: TC001 — dataclass field types
    LanguagePresenceResult,
    QuestionVariantResult,
    TranslationLinkResult,
)


@dataclass(frozen=True, slots=True)
class TranslatedAnswerResult:
    """The target language's new presence (with the translated answer) and its link."""

    presence: LanguagePresenceResult
    link: TranslationLinkResult


@dataclass(frozen=True, slots=True)
class TranslatedVariantResult:
    variant: QuestionVariantResult
    link: TranslationLinkResult
