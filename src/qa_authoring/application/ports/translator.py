from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qa_authoring.domain.model.glossary_guidance import GlossaryGuidance
    from qa_authoring.domain.model.language import Language


class UnsupportedLanguageForEngineError(Exception):
    def __init__(self, engine: str, language_code: str) -> None:
        super().__init__(f"the {engine} engine cannot translate language {language_code!r}")
        self.engine = engine
        self.language_code = language_code


class TranslationEngineError(Exception):
    """The engine failed. The message names the engine only, never provider internals."""

    def __init__(self, engine: str, reason: str = "failed") -> None:
        super().__init__(f"the {engine} translation engine {reason}")
        self.engine = engine


class TranslatorPort(Protocol):
    async def translate(
        self,
        text: str,
        source: Language,
        target: Language,
        glossary: tuple[GlossaryGuidance, ...] = (),
    ) -> str:
        """``text`` from ``source`` into ``target``, following the ``glossary`` guidance where
        the engine can. Raises ``UnsupportedLanguageForEngineError`` or
        ``TranslationEngineError``."""
        ...
