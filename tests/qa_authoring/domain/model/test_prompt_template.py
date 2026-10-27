from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    REQUIRED_PLACEHOLDERS,
    InvalidPromptTemplateError,
    PromptRenderError,
    PromptTemplate,
    PromptTemplateKey,
    placeholders,
)

T0 = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
TRANSLATION = PromptTemplateKey.TRANSLATION
VALID = "Translate from {source_language} to {target_language}:\n{text}"


def test_keys_and_their_required_placeholders() -> None:
    assert {k.value for k in PromptTemplateKey} == {
        "translation",
        "variant_generation",
        "completeness",
    }
    assert {
        PromptTemplateKey.COMPLETENESS: frozenset({"documentation", "answers", "language"}),
        PromptTemplateKey.TRANSLATION: frozenset({"source_language", "target_language", "text"}),
        PromptTemplateKey.VARIANT_GENERATION: frozenset(
            {"answer", "existing_questions", "context", "language"}
        ),
    } == REQUIRED_PLACEHOLDERS


def test_placeholders_ignore_escaped_braces() -> None:
    assert placeholders("A {x} and {{literal}} and {y} and {x}") == frozenset({"x", "y"})


def test_a_valid_template_is_accepted() -> None:
    template = PromptTemplate.create(TRANSLATION, VALID, updated_by=None, at=T0)
    assert (template.key, template.content, template.updated_by) == (TRANSLATION, VALID, None)


def test_missing_and_unknown_placeholders_are_listed() -> None:
    with pytest.raises(InvalidPromptTemplateError) as raised:
        PromptTemplate.create(
            TRANSLATION, "From {source_language}: {text} {tone}", updated_by=None, at=T0
        )
    assert raised.value.missing == ("target_language",)
    assert raised.value.unknown == ("tone",)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        VALID + " {}",
        VALID + " {0}",
        VALID + " {text.__class__}",
        VALID + " {text[0]}",
        VALID + " {text!r}",
        VALID + " {text:>10}",
        VALID + " {unclosed",
        VALID + " stray }",
    ],
)
def test_malformed_templates_are_rejected(content: str) -> None:
    with pytest.raises(InvalidPromptTemplateError):
        PromptTemplate.create(TRANSLATION, content, updated_by=None, at=T0)


def test_revise_validates_and_records_who_and_when() -> None:
    template = PromptTemplate.create(TRANSLATION, VALID, updated_by=None, at=T0)
    editor = uuid4()
    later = datetime(2026, 10, 25, tzinfo=UTC)

    template.revise(VALID + "\nBe faithful.", updated_by=editor, at=later)

    assert (template.content, template.updated_by, template.updated_at) == (
        VALID + "\nBe faithful.",
        editor,
        later,
    )
    with pytest.raises(InvalidPromptTemplateError):
        template.revise("{text}", updated_by=editor, at=later)
    assert template.content == VALID + "\nBe faithful."


def test_render_substitutes_values_and_keeps_literal_braces() -> None:
    template = PromptTemplate.create(
        TRANSLATION,
        'Return JSON like {{"translation": "..."}} from {source_language} to '
        "{target_language}: {text}",
        updated_by=None,
        at=T0,
    )

    rendered = template.render(
        {"source_language": "French", "target_language": "Bambara", "text": "Buvez {beaucoup}"}
    )

    assert rendered == (
        'Return JSON like {"translation": "..."} from French to Bambara: Buvez {beaucoup}'
    )


def test_render_needs_exactly_the_template_values() -> None:
    template = PromptTemplate.create(TRANSLATION, VALID, updated_by=None, at=T0)
    with pytest.raises(PromptRenderError) as missing:
        template.render({"source_language": "French", "text": "x"})
    assert missing.value.missing == ("target_language",)
    with pytest.raises(PromptRenderError) as unexpected:
        template.render(
            {"source_language": "fr", "target_language": "bm", "text": "x", "tone": "warm"}
        )
    assert unexpected.value.unexpected == ("tone",)


def test_updated_at_must_be_aware() -> None:
    with pytest.raises(ValueError, match="timezone"):
        PromptTemplate.create(TRANSLATION, VALID, updated_by=None, at=datetime(2026, 10, 24))


@pytest.mark.parametrize("existing", ["- Que faire ?\n- Comment soigner ?", "(none)", ""])
def test_the_default_variant_prompt_is_seeded_with_the_question_answer_pair(
    existing: str,
) -> None:
    template = PromptTemplate.create(
        PromptTemplateKey.VARIANT_GENERATION,
        DEFAULT_TEMPLATES[PromptTemplateKey.VARIANT_GENERATION],
        updated_by=None,
        at=T0,
    )
    rendered = template.render(
        {
            "answer": "Buvez de l'eau.",
            "existing_questions": existing,
            "context": "Fièvre",
            "language": "French",
        }
    )
    assert "Buvez de l'eau." in rendered
    assert existing in rendered
    assert "{" not in rendered and "}" not in rendered
    lowered = rendered.lower()
    assert "new" in lowered and "distinct" in lowered
    assert "do not repeat" in lowered
    assert "style" in lowered and "register" in lowered
