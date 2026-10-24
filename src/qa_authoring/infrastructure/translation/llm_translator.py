from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.ports.llm import LlmUnavailableError
from qa_authoring.application.ports.translator import TranslationEngineError
from qa_authoring.domain.model.prompt_template import PromptTemplateKey

if TYPE_CHECKING:
    from qa_authoring.application.ports.llm import LlmPort
    from qa_authoring.application.ports.prompt_templates import PromptTemplatePort
    from qa_authoring.domain.model.language import Language

ENGINE = "llm"


class LlmTranslator:
    """Translates with a language model, prompted by the organization's active ``translation``
    template (never a hardcoded prompt), given the languages' human-readable names."""

    def __init__(self, prompts: PromptTemplatePort, llm: LlmPort) -> None:
        self._prompts = prompts
        self._llm = llm

    async def translate(self, text: str, source: Language, target: Language) -> str:
        prompt = await self._prompts.render(
            PromptTemplateKey.TRANSLATION,
            {"source_language": source.name, "target_language": target.name, "text": text},
        )
        try:
            translated = (await self._llm.generate(prompt)).strip()
        except LlmUnavailableError as exc:
            raise TranslationEngineError(ENGINE) from exc
        if not translated:
            raise TranslationEngineError(ENGINE, "returned an empty translation")
        return translated
