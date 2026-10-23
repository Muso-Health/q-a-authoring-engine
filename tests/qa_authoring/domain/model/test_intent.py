from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.domain.model.intent import Intent, normalize_intent_text
from qa_authoring.domain.model.qaset import (
    IntentNotAttachedError,
    QASet,
    QuestionVariantNotFoundError,
)
from qa_authoring.domain.value_objects.naming import InvalidTextError


@pytest.mark.parametrize("text", ["Dosage", " dosage ", "DOSAGE", "dOsAgE\n"])
def test_normalized_key_ignores_case_and_outer_whitespace(text: str) -> None:
    assert Intent.register(text).key == "dosage"


def test_normalized_key_collapses_inner_whitespace() -> None:
    assert normalize_intent_text("  Side \t effects \n of  ACT ") == "side effects of act"


def test_register_keeps_the_trimmed_original_text() -> None:
    intent = Intent.register("  Side effects of ACT ")
    assert isinstance(intent.id, UUID)
    assert intent.text == "Side effects of ACT"


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_text_must_not_be_blank(text: str) -> None:
    with pytest.raises(InvalidTextError):
        Intent.register(text)


FR = uuid4()


def _qaset() -> QASet:
    return QASet.create(theme_id=uuid4(), language_id=FR, answer_text="a")


def test_attach_is_idempotent_and_ordered() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    first, second = uuid4(), uuid4()

    assert qaset.attach_intent(variant.id, second) is True
    assert qaset.attach_intent(variant.id, first) is True
    assert qaset.attach_intent(variant.id, second) is False

    assert qaset.presence(FR).variants[0].intent_ids == (second, first)


def test_detach_removes_only_that_intent() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    other = qaset.add_variant(FR, "q2")
    kept, removed = uuid4(), uuid4()
    qaset.attach_intent(variant.id, kept)
    qaset.attach_intent(variant.id, removed)
    qaset.attach_intent(other.id, removed)

    qaset.detach_intent(variant.id, removed)

    variants = {v.id: v.intent_ids for v in qaset.variants}
    assert variants == {variant.id: (kept,), other.id: (removed,)}
    with pytest.raises(IntentNotAttachedError):
        qaset.detach_intent(variant.id, removed)


def test_attachment_needs_a_variant_of_this_qaset() -> None:
    qaset = _qaset()
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.attach_intent(uuid4(), uuid4())
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.detach_intent(uuid4(), uuid4())


def test_intents_do_not_propagate_across_translation_links() -> None:
    bm = uuid4()
    qaset = _qaset()
    qaset.add_language(bm, "b")
    fr_variant = qaset.add_variant(FR, "q")
    bm_variant = qaset.add_variant(bm, "q bm")
    qaset.link_variants(fr_variant.id, bm_variant.id)

    qaset.attach_intent(fr_variant.id, uuid4())

    assert qaset.presence(bm).variants[0].intent_ids == ()


def test_uses_intent() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    intent_id = uuid4()
    assert not qaset.uses_intent(intent_id)
    qaset.attach_intent(variant.id, intent_id)
    assert qaset.uses_intent(intent_id)
