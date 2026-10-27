from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.ports.llm import LlmUnavailableError
from qa_authoring.application.ports.variant_generator import GenerationEngineError
from qa_authoring.domain.model.prompt_template import PromptTemplateKey
from qa_authoring.infrastructure.llm.json_list import ListParseError, parse_string_list

if TYPE_CHECKING:
    from qa_authoring.application.ports.llm import LlmPort
    from qa_authoring.application.ports.prompt_templates import PromptTemplatePort
    from qa_authoring.domain.model.language import Language

# Appended to the editable template: the machine contract never depends on what editors write.
OUTPUT_DIRECTIVE = (
    "\n\nOutput format: reply with a JSON array of strings, one question per element, and "
    "nothing else: no numbering, no commentary, no Markdown."
)


class LlmVariantGenerator:
    """Proposes question variants with a language model, prompted by the organization's active
    ``variant_generation`` template plus a fixed output directive, and parses the reply."""

    def __init__(self, prompts: PromptTemplatePort, llm: LlmPort) -> None:
        self._prompts = prompts
        self._llm = llm

    async def generate(
        self, answer: str, existing_questions: tuple[str, ...], context: str, language: Language
    ) -> tuple[str, ...]:
        prompt = await self._prompts.render(
            PromptTemplateKey.VARIANT_GENERATION,
            {
                "answer": answer,
                "existing_questions": "\n".join(f"- {q}" for q in existing_questions) or "(none)",
                "context": context.strip() or "(none)",
                "language": language.name,
            },
        )
        try:
            reply = await self._llm.generate(prompt + OUTPUT_DIRECTIVE)
        except LlmUnavailableError as exc:
            raise GenerationEngineError() from exc
        return parse_candidates(reply)


def parse_candidates(reply: str) -> tuple[str, ...]:
    try:
        return parse_string_list(reply)
    except ListParseError as exc:
        raise GenerationEngineError(str(exc)) from exc


class UnavailableVariantGenerator:
    """Stands in when no language model is configured."""

    async def generate(
        self, answer: str, existing_questions: tuple[str, ...], context: str, language: Language
    ) -> tuple[str, ...]:
        raise GenerationEngineError("is not configured")
