from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.ports.completeness_analyzer import CompletenessEngineError
from qa_authoring.application.ports.llm import LlmUnavailableError
from qa_authoring.domain.model.prompt_template import PromptTemplateKey
from qa_authoring.infrastructure.llm.json_list import ListParseError, parse_string_list

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.ports.llm import LlmPort
    from qa_authoring.application.ports.prompt_templates import PromptTemplatePort
    from qa_authoring.domain.model.language import Language

# Appended to the editable template: the machine contract never depends on what editors write.
OUTPUT_DIRECTIVE = (
    "\n\nOutput format: reply with a JSON array of strings, one uncovered notion per element "
    "([] if every notion is covered), and nothing else: no commentary, no Markdown."
)


class LlmCompletenessAnalyzer:
    """Finds uncovered notions with a language model, prompted by the organization's active
    ``completeness`` template plus a fixed output directive."""

    def __init__(self, prompts: PromptTemplatePort, llm: LlmPort) -> None:
        self._prompts = prompts
        self._llm = llm

    async def analyze(
        self, documentation: str, answers: Sequence[str], language: Language
    ) -> tuple[str, ...]:
        listed = "\n".join(f"- {answer}" for answer in answers) or "(none)"
        prompt = await self._prompts.render(
            PromptTemplateKey.COMPLETENESS,
            {"documentation": documentation, "answers": listed, "language": language.name},
        )
        try:
            reply = await self._llm.generate(prompt + OUTPUT_DIRECTIVE)
            return parse_string_list(reply, allow_empty=True)
        except (LlmUnavailableError, ListParseError) as exc:
            raise CompletenessEngineError() from exc


class UnavailableCompletenessAnalyzer:
    """Stands in when no language model is configured."""

    async def analyze(
        self, documentation: str, answers: Sequence[str], language: Language
    ) -> tuple[str, ...]:
        raise CompletenessEngineError("is not configured")
