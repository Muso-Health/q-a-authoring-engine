from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.domain.model.qaset import (
    LanguageAlreadyPresentError,
    LanguageNotPresentError,
    LanguagePresenceRequiredError,
    QASet,
    QuestionVariantNotFoundError,
)
from qa_authoring.domain.value_objects.naming import InvalidTextError

FR = UUID("00000000-0000-0000-0000-00000000000f")
BM = UUID("00000000-0000-0000-0000-0000000000b0")


def _qaset() -> QASet:
    return QASet.create(theme_id=uuid4(), language_id=FR, answer_text="  Rest and fluids. ")


def test_create_has_one_answer_and_no_variants() -> None:
    qaset = _qaset()
    assert isinstance(qaset.id, UUID)
    [presence] = qaset.presences()
    assert presence.language_id == FR
    assert presence.answer.text == "Rest and fluids."
    assert presence.variants == ()
    assert presence.variant_count == 0


@pytest.mark.parametrize("text", ["", "  ", "\n"])
def test_answer_text_must_not_be_blank(text: str) -> None:
    with pytest.raises(InvalidTextError):
        QASet.create(theme_id=uuid4(), language_id=FR, answer_text=text)


def test_one_answer_per_language() -> None:
    qaset = _qaset()
    with pytest.raises(LanguageAlreadyPresentError):
        qaset.add_language(FR, "Again")
    assert len(qaset.presences()) == 1


def test_add_language_and_update_answer() -> None:
    qaset = _qaset()
    answer = qaset.add_language(BM, "Bambara answer")
    qaset.update_answer(BM, "  Edited ")
    presence = qaset.presence(BM)
    assert presence.answer.id == answer.id
    assert presence.answer.text == "Edited"


def test_update_answer_of_an_absent_language() -> None:
    with pytest.raises(LanguageNotPresentError):
        _qaset().update_answer(BM, "x")


def test_variant_requires_a_language_presence() -> None:
    qaset = _qaset()
    with pytest.raises(LanguagePresenceRequiredError):
        qaset.add_variant(BM, "Is it serious?")
    assert qaset.presence(FR).variants == ()


def test_variants_are_grouped_by_language() -> None:
    qaset = _qaset()
    qaset.add_language(BM, "Bambara answer")
    qaset.add_variant(FR, "What to do?")
    qaset.add_variant(FR, "How to treat it?")
    qaset.add_variant(BM, "Bambara question")

    counts = {p.language_id: p.variant_count for p in qaset.presences()}

    assert counts == {FR: 2, BM: 1}
    assert {v.text for v in qaset.presence(FR).variants} == {"What to do?", "How to treat it?"}


def test_removing_a_presence_drops_its_variants() -> None:
    qaset = _qaset()
    qaset.add_language(BM, "Bambara answer")
    qaset.add_variant(BM, "Bambara question")
    kept = qaset.add_variant(FR, "What to do?")

    qaset.remove_language(BM)

    assert [p.language_id for p in qaset.presences()] == [FR]
    assert [v.id for v in qaset.variants] == [kept.id]
    with pytest.raises(LanguageNotPresentError):
        qaset.remove_language(BM)


def test_update_and_remove_variant() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "What to do?")

    qaset.update_variant(variant.id, " What should I do? ")
    assert qaset.presence(FR).variants[0].text == "What should I do?"
    with pytest.raises(InvalidTextError):
        qaset.update_variant(variant.id, " ")

    qaset.remove_variant(variant.id)
    assert qaset.variants == ()
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.remove_variant(variant.id)
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.update_variant(uuid4(), "x")


def test_variant_text_must_not_be_blank() -> None:
    with pytest.raises(InvalidTextError):
        _qaset().add_variant(FR, "  ")


def test_theme_is_immutable() -> None:
    qaset = _qaset()
    with pytest.raises(AttributeError):
        qaset.theme_id = uuid4()  # type: ignore[misc]


@pytest.mark.usefixtures("descending_uuids")
def test_presences_and_variants_keep_creation_order() -> None:
    # FR > BM as UUIDs and every new id is smaller than the last: creation order must win.
    qaset = QASet.create(theme_id=uuid4(), language_id=FR, answer_text="a")
    qaset.add_language(BM, "b")
    texts = [f"q{i}" for i in range(5)]
    for text in texts:
        qaset.add_variant(FR, text)

    assert [p.language_id for p in qaset.presences()] == [FR, BM]
    assert [v.text for v in qaset.presence(FR).variants] == texts
    qaset.update_answer(FR, "edited")
    qaset.update_variant(qaset.presence(FR).variants[0].id, "q0 edited")
    assert [p.language_id for p in qaset.presences()] == [FR, BM]
    assert [v.text for v in qaset.presence(FR).variants][1:] == texts[1:]


def test_rehydrate_rejects_a_variant_without_presence() -> None:
    qaset = _qaset()
    variant = qaset.add_variant(FR, "q")
    with pytest.raises(LanguagePresenceRequiredError):
        QASet(qaset.id, qaset.theme_id, answers=(), variants=(variant,))
