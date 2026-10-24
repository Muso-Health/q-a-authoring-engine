from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from google.api_core.exceptions import InvalidArgument, ServiceUnavailable

from qa_authoring.application.ports.translator import (
    TranslationEngineError,
    UnsupportedLanguageForEngineError,
)
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.prompt_template import PromptTemplateKey
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.translation.google_translator import GoogleTranslator
from qa_authoring.infrastructure.translation.llm_translator import LlmTranslator
from tests.fakes import FakeLlm

if TYPE_CHECKING:
    from collections.abc import Mapping

FRENCH = Language.register(LanguageCode("fr"), "French")
BAMBARA = Language.register(LanguageCode("bm"), "Bambara")
EN_GB = Language.register(LanguageCode("en_gb"), "British English")


class FakePrompts:
    def __init__(self) -> None:
        self.calls: list[tuple[PromptTemplateKey, dict[str, str]]] = []

    async def render(self, key: PromptTemplateKey, values: Mapping[str, str]) -> str:
        self.calls.append((key, dict(values)))
        return "PROMPT " + " | ".join(f"{k}={v}" for k, v in sorted(values.items()))


# --- LLM ---


async def test_llm_translator_renders_the_translation_template_with_names() -> None:
    prompts, llm = FakePrompts(), FakeLlm()

    translated = await LlmTranslator(prompts, llm).translate("Buvez de l'eau.", FRENCH, BAMBARA)

    assert prompts.calls == [
        (
            PromptTemplateKey.TRANSLATION,
            {"source_language": "French", "target_language": "Bambara", "text": "Buvez de l'eau."},
        )
    ]
    assert llm.prompts == [
        "PROMPT source_language=French | target_language=Bambara | text=Buvez de l'eau."
    ]
    assert translated == "Traduction du modèle"


@pytest.mark.parametrize("reply", ["", "   \n"])
async def test_llm_translator_refuses_an_empty_reply(reply: str) -> None:
    llm = FakeLlm()
    llm.reply = reply
    with pytest.raises(TranslationEngineError):
        await LlmTranslator(FakePrompts(), llm).translate("x", FRENCH, BAMBARA)


async def test_llm_translator_maps_model_failures() -> None:
    llm = FakeLlm()
    llm.failing = True
    with pytest.raises(TranslationEngineError) as raised:
        await LlmTranslator(FakePrompts(), llm).translate("x", FRENCH, BAMBARA)
    assert raised.value.engine == "llm"


# --- Google ---


def _language(code: str, *, source: bool = True, target: bool = True) -> Any:
    return SimpleNamespace(language_code=code, support_source=source, support_target=target)


class FakeTranslationClient:
    """Mimics ``TranslationServiceAsyncClient``: the two calls the adapter makes."""

    def __init__(self, languages: list[Any]) -> None:
        self.languages = languages
        self.supported_calls: list[str] = []
        self.requests: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def get_supported_languages(self, *, parent: str) -> Any:
        self.supported_calls.append(parent)
        return SimpleNamespace(languages=self.languages)

    async def translate_text(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        text = request["contents"][0]
        return SimpleNamespace(translations=[SimpleNamespace(translated_text=f"<{text}>")])


def _google(client: FakeTranslationClient, project: str = "proj") -> GoogleTranslator:
    return GoogleTranslator(project=project, location="global", client_factory=lambda: client)


async def test_google_translates_with_mapped_codes_and_caches_the_language_list() -> None:
    client = FakeTranslationClient([_language("fr"), _language("en-GB"), _language("bm")])
    google = _google(client)

    first = await google.translate("Bonjour", FRENCH, EN_GB)
    await google.translate("Merci", FRENCH, BAMBARA)

    assert first == "<Bonjour>"
    assert client.requests[0] == {
        "parent": "projects/proj/locations/global",
        "contents": ["Bonjour"],
        "mime_type": "text/plain",
        "source_language_code": "fr",
        "target_language_code": "en-GB",
    }
    assert client.supported_calls == ["projects/proj/locations/global"]


@pytest.mark.parametrize(
    ("languages", "source", "target", "unsupported"),
    [
        ([_language("fr")], FRENCH, BAMBARA, "bm"),
        ([_language("fr"), _language("bm", target=False)], FRENCH, BAMBARA, "bm"),
        ([_language("bm"), _language("fr", source=False)], FRENCH, BAMBARA, "fr"),
    ],
)
async def test_google_refuses_unsupported_languages_before_translating(
    languages: list[Any], source: Language, target: Language, unsupported: str
) -> None:
    client = FakeTranslationClient(languages)
    with pytest.raises(UnsupportedLanguageForEngineError) as raised:
        await _google(client).translate("x", source, target)
    assert (raised.value.engine, raised.value.language_code) == ("google", unsupported)
    assert client.requests == []


_SDK_ERRORS = [
    ServiceUnavailable("down"),  # type: ignore[no-untyped-call]
    InvalidArgument("bad"),  # type: ignore[no-untyped-call]
]


@pytest.mark.parametrize("error", _SDK_ERRORS)
async def test_google_maps_sdk_errors(error: Exception) -> None:
    client = FakeTranslationClient([_language("fr"), _language("bm")])
    client.error = error
    with pytest.raises(TranslationEngineError) as raised:
        await _google(client).translate("x", FRENCH, BAMBARA)
    assert raised.value.engine == "google"
    assert "down" not in str(raised.value) and "bad" not in str(raised.value)


async def test_google_without_a_project_is_an_engine_error() -> None:
    client = FakeTranslationClient([_language("fr"), _language("bm")])
    with pytest.raises(TranslationEngineError, match="not configured"):
        await _google(client, project="").translate("x", FRENCH, BAMBARA)
