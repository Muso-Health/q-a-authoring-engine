from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    LinkAlreadyExistsError,
    QASet,
    QuestionVariantNotFoundError,
    SameLanguageError,
    SelfLinkError,
    TranslationLink,
    TranslationLinkNotFoundError,
)

FR, BM, EN = uuid4(), uuid4(), uuid4()


def _qaset() -> QASet:
    qaset = QASet.create(theme_id=uuid4(), language_id=FR, answer_text="fr")
    qaset.add_language(BM, "bm")
    qaset.add_language(EN, "en")
    return qaset


def _answer(qaset: QASet, language_id: UUID) -> UUID:
    return qaset.presence(language_id).answer.id


def test_link_is_canonical_regardless_of_argument_order() -> None:
    low, high = sorted([uuid4(), uuid4()])
    reversed_link = TranslationLink.between(uuid4(), high, low)
    assert (reversed_link.low_id, reversed_link.high_id) == (low, high)
    link = TranslationLink.between(uuid4(), low, high)
    assert (link.low_id, link.high_id) == (low, high)
    assert link.other(low) == high
    assert link.other(high) == low


def test_answer_link_is_symmetric() -> None:
    qaset = _qaset()
    fr, bm = _answer(qaset, FR), _answer(qaset, BM)

    link = qaset.link_answers(bm, fr)

    [from_fr] = qaset.answer_translations(fr)
    [from_bm] = qaset.answer_translations(bm)
    assert (from_fr.link_id, from_fr.other_id, from_fr.other_language_id) == (link.id, bm, BM)
    assert (from_bm.link_id, from_bm.other_id, from_bm.other_language_id) == (link.id, fr, FR)


def test_rejects_self_link() -> None:
    qaset = _qaset()
    fr = _answer(qaset, FR)
    with pytest.raises(SelfLinkError):
        qaset.link_answers(fr, fr)


def test_rejects_same_language() -> None:
    qaset = _qaset()
    first = qaset.add_variant(FR, "q1")
    second = qaset.add_variant(FR, "q2")
    with pytest.raises(SameLanguageError):
        qaset.link_variants(first.id, second.id)


def test_rejects_a_duplicate_in_either_direction() -> None:
    qaset = _qaset()
    fr, bm = _answer(qaset, FR), _answer(qaset, BM)
    qaset.link_answers(fr, bm)
    with pytest.raises(LinkAlreadyExistsError):
        qaset.link_answers(fr, bm)
    with pytest.raises(LinkAlreadyExistsError):
        qaset.link_answers(bm, fr)
    assert len(qaset.answer_links) == 1


def test_allows_several_counterparts_in_the_same_language() -> None:
    qaset = _qaset()
    fr = qaset.add_variant(FR, "fr question")
    bm_one = qaset.add_variant(BM, "bm question 1")
    bm_two = qaset.add_variant(BM, "bm question 2")

    qaset.link_variants(fr.id, bm_one.id)
    qaset.link_variants(fr.id, bm_two.id)

    others = [t.other_id for t in qaset.variant_translations(fr.id)]
    assert others == [bm_one.id, bm_two.id]
    assert [t.other_id for t in qaset.variant_translations(bm_one.id)] == [fr.id]


def test_items_must_belong_to_the_qaset() -> None:
    qaset = _qaset()
    fr = _answer(qaset, FR)
    variant = qaset.add_variant(FR, "q")
    with pytest.raises(AnswerNotFoundError):
        qaset.link_answers(fr, uuid4())
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.link_variants(uuid4(), variant.id)
    # An answer id is not a variant id: the kinds never mix.
    with pytest.raises(QuestionVariantNotFoundError):
        qaset.link_variants(variant.id, fr)


def test_unlink_removes_only_that_link() -> None:
    qaset = _qaset()
    fr, bm, en = _answer(qaset, FR), _answer(qaset, BM), _answer(qaset, EN)
    removed = qaset.link_answers(fr, bm)
    kept = qaset.link_answers(fr, en)

    qaset.unlink_answers(removed.id)

    assert qaset.answer_links == (kept,)
    with pytest.raises(TranslationLinkNotFoundError):
        qaset.unlink_answers(removed.id)
    with pytest.raises(TranslationLinkNotFoundError):
        qaset.unlink_variants(kept.id)


def test_removing_items_drops_their_links() -> None:
    qaset = _qaset()
    fr_variant = qaset.add_variant(FR, "fr q")
    bm_variant = qaset.add_variant(BM, "bm q")
    en_variant = qaset.add_variant(EN, "en q")
    qaset.link_variants(fr_variant.id, bm_variant.id)
    kept = qaset.link_variants(fr_variant.id, en_variant.id)
    qaset.link_answers(_answer(qaset, FR), _answer(qaset, BM))
    kept_answer_link = qaset.link_answers(_answer(qaset, FR), _answer(qaset, EN))

    qaset.remove_language(BM)

    assert qaset.variant_links == (kept,)
    assert qaset.answer_links == (kept_answer_link,)

    qaset.remove_variant(en_variant.id)
    assert len(qaset.variant_links) == 0


def test_rehydrate_validates_links() -> None:
    qaset = _qaset()
    fr, bm = _answer(qaset, FR), _answer(qaset, BM)
    link = qaset.link_answers(fr, bm)
    rebuilt = QASet(
        qaset.id,
        qaset.theme_id,
        answers=qaset.answers,
        variants=(),
        answer_links=(link,),
        variant_links=(),
    )
    assert rebuilt.answer_links == (link,)
    with pytest.raises(AnswerNotFoundError):
        QASet(
            qaset.id,
            qaset.theme_id,
            answers=qaset.answers[:1],
            variants=(),
            answer_links=(link,),
            variant_links=(),
        )
