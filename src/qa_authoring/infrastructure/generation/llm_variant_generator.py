from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from qa_authoring.application.ports.llm import LlmUnavailableError
from qa_authoring.application.ports.variant_generator import GenerationEngineError
from qa_authoring.domain.model.prompt_template import PromptTemplateKey

if TYPE_CHECKING:
    from qa_authoring.application.ports.llm import LlmPort
    from qa_authoring.application.ports.prompt_templates import PromptTemplatePort
    from qa_authoring.domain.model.language import Language

# Appended to the editable template: the machine contract never depends on what editors write.
OUTPUT_DIRECTIVE = (
    "\n\nOutput format: reply with a JSON array of strings, one question per element, and "
    "nothing else: no numbering, no commentary, no Markdown."
)

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LlmVariantGenerator:
    """Proposes question variants with a language model, prompted by the organization's active
    ``variant_generation`` template plus a fixed output directive, and parses the reply."""

    def __init__(self, prompts: PromptTemplatePort, llm: LlmPort) -> None:
        self._prompts = prompts
        self._llm = llm

    async def generate(self, answer: str, context: str, language: Language) -> tuple[str, ...]:
        prompt = await self._prompts.render(
            PromptTemplateKey.VARIANT_GENERATION,
            {"answer": answer, "context": context.strip() or "(none)", "language": language.name},
        )
        try:
            reply = await self._llm.generate(prompt + OUTPUT_DIRECTIVE)
        except LlmUnavailableError as exc:
            raise GenerationEngineError() from exc
        return parse_candidates(reply)


def parse_candidates(reply: str) -> tuple[str, ...]:
    """The JSON array of strings in ``reply``, trimmed, without blanks or duplicates (ignoring
    case; the first spelling wins). A Markdown fence or prose around the array is tolerated."""
    text = reply.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    parsed = _json_array(text)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise GenerationEngineError("did not return a list of questions")
    candidates: dict[str, str] = {}
    for item in parsed:
        candidate = " ".join(item.split())
        if candidate:
            candidates.setdefault(candidate.casefold(), candidate)
    if not candidates:
        raise GenerationEngineError("returned no questions")
    return tuple(candidates.values())


def _json_array(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            raise GenerationEngineError("did not return a list of questions") from None
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            raise GenerationEngineError("did not return a list of questions") from None


class UnavailableVariantGenerator:
    """Stands in when no language model is configured."""

    async def generate(self, answer: str, context: str, language: Language) -> tuple[str, ...]:
        raise GenerationEngineError("is not configured")
