from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from qa_authoring.application.ports.variant_generator import GenerationEngineError
from qa_authoring.domain.model.language import Language
from qa_authoring.domain.model.prompt_template import PromptTemplateKey
from qa_authoring.domain.value_objects.language_code import LanguageCode
from qa_authoring.infrastructure.generation.llm_variant_generator import (
    OUTPUT_DIRECTIVE,
    LlmVariantGenerator,
)
from tests.fakes import FakeLlm

if TYPE_CHECKING:
    from collections.abc import Mapping

FRENCH = Language.register(LanguageCode("fr"), "French")


class FakePrompts:
    def __init__(
        self,
        template: str = (
            "ANSWER={answer} QUESTIONS={existing_questions} CONTEXT={context} LANGUAGE={language}"
        ),
    ) -> None:
        self.template = template
        self.calls: list[tuple[PromptTemplateKey, dict[str, str]]] = []

    async def render(self, key: PromptTemplateKey, values: Mapping[str, str]) -> str:
        self.calls.append((key, dict(values)))
        return self.template.format_map(values)


def _generator(
    reply: str, prompts: FakePrompts | None = None
) -> tuple[LlmVariantGenerator, FakeLlm]:
    llm = FakeLlm()
    llm.reply = reply
    return LlmVariantGenerator(prompts or FakePrompts(), llm), llm


async def test_renders_the_template_and_appends_the_fixed_directive() -> None:
    prompts = FakePrompts()
    generator, llm = _generator('["Que faire ?"]', prompts)

    await generator.generate(
        "Buvez de l'eau.", ("Que faire ?", "Comment soigner ?"), " Fièvre chez l'enfant ", FRENCH
    )

    assert prompts.calls == [
        (
            PromptTemplateKey.VARIANT_GENERATION,
            {
                "answer": "Buvez de l'eau.",
                "existing_questions": "- Que faire ?\n- Comment soigner ?",
                "context": "Fièvre chez l'enfant",
                "language": "French",
            },
        )
    ]
    [prompt] = llm.prompts
    assert prompt.startswith(
        "ANSWER=Buvez de l'eau. QUESTIONS=- Que faire ?\n- Comment soigner ? "
        "CONTEXT=Fièvre chez l'enfant LANGUAGE=French"
    )
    assert prompt.endswith(OUTPUT_DIRECTIVE)
    assert "JSON array of strings" in OUTPUT_DIRECTIVE


async def test_an_empty_context_or_no_existing_question_is_marked_as_none() -> None:
    prompts = FakePrompts()
    generator, _ = _generator('["q"]', prompts)
    await generator.generate("a", (), "   ", FRENCH)
    values = prompts.calls[0][1]
    assert (values["context"], values["existing_questions"]) == ("(none)", "(none)")


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (
            '["Que faire ?", "Comment soigner la fièvre ?"]',
            ("Que faire ?", "Comment soigner la fièvre ?"),
        ),
        (
            '  [" Que faire ? ", "", "  ", "que faire ?", "Et après ?"]  ',
            ("Que faire ?", "Et après ?"),
        ),
        ('```json\n["Que faire ?"]\n```', ("Que faire ?",)),
        (
            'Here are the questions:\n["Que faire ?", "Et après ?"]\nHope this helps.',
            ("Que faire ?", "Et après ?"),
        ),
    ],
)
async def test_parses_trims_and_deduplicates(reply: str, expected: tuple[str, ...]) -> None:
    generator, _ = _generator(reply)
    assert await generator.generate("a", (), "", FRENCH) == expected


@pytest.mark.parametrize(
    "reply",
    [
        "Que faire ?\nEt après ?",
        '{"questions": ["Que faire ?"]}',
        '["Que faire ?", 3]',
        "[]",
        '["", "  "]',
        "[not json]",
    ],
)
async def test_unusable_output_is_an_engine_error(reply: str) -> None:
    generator, _ = _generator(reply)
    with pytest.raises(GenerationEngineError):
        await generator.generate("a", (), "", FRENCH)


async def test_model_failures_are_engine_errors() -> None:
    generator, llm = _generator('["q"]')
    llm.failing = True
    with pytest.raises(GenerationEngineError):
        await generator.generate("a", (), "", FRENCH)


async def test_editing_the_template_does_not_change_the_contract() -> None:
    edited = FakePrompts(
        "Write in {language}. Make them short.\n{context}\n---\n{answer}\n{existing_questions}"
    )
    generator, llm = _generator('["Que faire ?"]', edited)

    assert await generator.generate("Buvez.", (), "", FRENCH) == ("Que faire ?",)
    assert llm.prompts[0].endswith(OUTPUT_DIRECTIVE)
