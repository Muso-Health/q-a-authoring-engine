from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from qa_authoring.application.ports.completeness_analyzer import CompletenessEngineError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.prompt_template import PromptTemplateKey
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.completeness.llm_completeness_analyzer import (
    OUTPUT_DIRECTIVE,
    LlmCompletenessAnalyzer,
)
from tests.fakes import FakeLlm

if TYPE_CHECKING:
    from collections.abc import Mapping

FRENCH = Language.register(LanguageCode("fr"), "French")


class FakePrompts:
    def __init__(self) -> None:
        self.calls: list[tuple[PromptTemplateKey, dict[str, str]]] = []

    async def render(self, key: PromptTemplateKey, values: Mapping[str, str]) -> str:
        self.calls.append((key, dict(values)))
        return "DOC={documentation}\nANSWERS={answers}\nLANG={language}".format_map(values)


def _analyzer(reply: str) -> tuple[LlmCompletenessAnalyzer, FakePrompts, FakeLlm]:
    prompts, llm = FakePrompts(), FakeLlm()
    llm.reply = reply
    return LlmCompletenessAnalyzer(prompts, llm), prompts, llm


async def test_renders_the_completeness_template_with_the_fixed_directive() -> None:
    analyzer, prompts, llm = _analyzer('["Prévention", "Dosage chez l\'enfant"]')

    notions = await analyzer.analyze(
        "Le paludisme...", ("Buvez.", "Dormez sous une moustiquaire."), FRENCH
    )

    assert notions == ("Prévention", "Dosage chez l'enfant")
    [(key, values)] = prompts.calls
    assert key is PromptTemplateKey.COMPLETENESS
    assert values == {
        "documentation": "Le paludisme...",
        "answers": "- Buvez.\n- Dormez sous une moustiquaire.",
        "language": "French",
    }
    assert llm.prompts[0].endswith(OUTPUT_DIRECTIVE)
    assert "JSON array of strings" in OUTPUT_DIRECTIVE


async def test_no_answers_yet_is_said_explicitly() -> None:
    analyzer, prompts, _ = _analyzer('["Everything"]')
    await analyzer.analyze("doc", (), FRENCH)
    assert prompts.calls[0][1]["answers"] == "(none)"


async def test_an_empty_list_means_everything_is_covered() -> None:
    analyzer, _, _ = _analyzer("[]")
    assert await analyzer.analyze("doc", ("a",), FRENCH) == ()


@pytest.mark.parametrize("reply", ["Prevention, dosage", '{"notions": []}', '["a", 1]', ""])
async def test_unusable_output_is_an_engine_error(reply: str) -> None:
    analyzer, _, _ = _analyzer(reply)
    with pytest.raises(CompletenessEngineError):
        await analyzer.analyze("doc", ("a",), FRENCH)


async def test_model_failure_is_an_engine_error() -> None:
    analyzer, _, llm = _analyzer("[]")
    llm.failing = True
    with pytest.raises(CompletenessEngineError):
        await analyzer.analyze("doc", ("a",), FRENCH)
