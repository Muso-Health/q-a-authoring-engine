from __future__ import annotations

from typing import TYPE_CHECKING, Any

from google.api_core.exceptions import GoogleAPICallError

from qa_authoring.application.ports.translator import (
    TranslationEngineError,
    UnsupportedLanguageForEngineError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from qa_authoring.domain.model.language import Language

ENGINE = "google"


def _default_client() -> Any:
    from google.cloud import translate_v3

    return translate_v3.TranslationServiceAsyncClient()


def engine_code(language: Language) -> str:
    """Internal codes are lowercase ``_``-separated (``en_gb``); Google uses BCP-47 (``en-GB``)."""
    head, *rest = language.code.value.split("_")
    return "-".join([head, *(part.upper() for part in rest)])


class GoogleTranslator:
    """Translates with Google Cloud Translation (v3, Application Default Credentials). Whether a
    language is supported comes from Google's own language list, fetched once; unsupported
    languages are refused before any translation request."""

    def __init__(
        self,
        *,
        project: str,
        location: str,
        client_factory: Callable[[], Any] = _default_client,
    ) -> None:
        self._project = project
        self._location = location
        self._client_factory = client_factory
        self._client: Any = None
        self._sources: frozenset[str] | None = None
        self._targets: frozenset[str] | None = None

    async def translate(self, text: str, source: Language, target: Language) -> str:
        if not self._project:
            raise TranslationEngineError(ENGINE, "is not configured")
        source_code, target_code = engine_code(source), engine_code(target)
        try:
            sources, targets = await self._supported()
            if source_code.lower() not in sources:
                raise UnsupportedLanguageForEngineError(ENGINE, source.code.value)
            if target_code.lower() not in targets:
                raise UnsupportedLanguageForEngineError(ENGINE, target.code.value)
            response = await self._client.translate_text(
                parent=self._parent,
                contents=[text],
                mime_type="text/plain",
                source_language_code=source_code,
                target_language_code=target_code,
            )
        except GoogleAPICallError as exc:
            raise TranslationEngineError(ENGINE) from exc
        return str(response.translations[0].translated_text)

    @property
    def _parent(self) -> str:
        return f"projects/{self._project}/locations/{self._location}"

    async def _supported(self) -> tuple[frozenset[str], frozenset[str]]:
        if self._client is None:
            self._client = self._client_factory()
        if self._sources is None or self._targets is None:
            response = await self._client.get_supported_languages(parent=self._parent)
            languages = list(response.languages)
            self._sources = frozenset(
                lang.language_code.lower() for lang in languages if lang.support_source
            )
            self._targets = frozenset(
                lang.language_code.lower() for lang in languages if lang.support_target
            )
        return self._sources, self._targets
