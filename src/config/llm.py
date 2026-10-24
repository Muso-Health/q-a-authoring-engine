from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.infrastructure.llm.gemini import GeminiLlm
from qa_authoring.infrastructure.translation.google_translator import GoogleTranslator

if TYPE_CHECKING:
    from config.settings import Settings
    from qa_authoring.application.ports.llm import LlmPort
    from qa_authoring.application.ports.translator import TranslatorPort


def llm_from_settings(settings: Settings) -> LlmPort:
    """The configured language model provider (only Gemini so far)."""
    return GeminiLlm(
        model=settings.llm_model,
        project=settings.llm_project,
        location=settings.llm_location,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def google_translator_from_settings(settings: Settings) -> TranslatorPort:
    return GoogleTranslator(
        project=settings.google_translate_project, location=settings.google_translate_location
    )
