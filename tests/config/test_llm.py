from __future__ import annotations

from typing import TYPE_CHECKING

from config.llm import google_translator_from_settings, llm_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.llm.gemini import GeminiLlm
from qa_authoring.infrastructure.translation.google_translator import GoogleTranslator

if TYPE_CHECKING:
    import pytest


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_gemini_is_the_default_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(llm_from_settings(_settings(monkeypatch)), GeminiLlm)


def test_google_translator_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    translator = google_translator_from_settings(
        _settings(monkeypatch, GOOGLE_TRANSLATE_PROJECT="proj")
    )
    assert isinstance(translator, GoogleTranslator)
