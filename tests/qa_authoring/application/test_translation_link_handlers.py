from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.application.link_answers.command import LinkAnswersCommand
from qa_authoring.application.link_answers.handler import LinkAnswersHandler
from qa_authoring.application.link_variants.command import LinkVariantsCommand
from qa_authoring.application.link_variants.handler import LinkVariantsHandler
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.application.unlink_answers.command import UnlinkAnswersCommand
from qa_authoring.application.unlink_answers.handler import UnlinkAnswersHandler
from qa_authoring.application.unlink_variants.command import UnlinkVariantsCommand
from qa_authoring.application.unlink_variants.handler import UnlinkVariantsHandler
from qa_authoring.domain.model.qaset import (
    AnswerNotFoundError,
    LinkAlreadyExistsError,
    QASet,
    QuestionVariantNotFoundError,
    SameLanguageError,
    SelfLinkError,
    TranslationLinkNotFoundError,
)
from tests.fakes import InMemoryStore

FR, BM, EN = uuid4(), uuid4(), uuid4()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


async def _qaset(store: InMemoryStore) -> QASet:
    qaset = QASet.create(theme_id=uuid4(), language_id=FR, answer_text="fr")
    qaset.add_language(BM, "bm")
    qaset.add_language(EN, "en")
    qaset.add_variant(FR, "fr q")
    qaset.add_variant(BM, "bm q1")
    qaset.add_variant(BM, "bm q2")
    await store.qasets.add(qaset)
    return qaset


def _answer(qaset: QASet, language_id: UUID) -> UUID:
    return qaset.presence(language_id).answer.id


def _variant(qaset: QASet, language_id: UUID, index: int = 0) -> UUID:
    return qaset.presence(language_id).variants[index].id


async def _link_answers(store: InMemoryStore, qaset_id: UUID, a: UUID, b: UUID) -> UUID:
    result = await LinkAnswersHandler(store.qasets)(
        LinkAnswersCommand(qaset_id=qaset_id, answer_a_id=a, answer_b_id=b)
    )
    return result.id


async def test_link_answers_persists_a_canonical_link(store: InMemoryStore) -> None:
    qaset = await _qaset(store)
    fr, bm = _answer(qaset, FR), _answer(qaset, BM)

    result = await LinkAnswersHandler(store.qasets)(
        LinkAnswersCommand(qaset_id=qaset.id, answer_a_id=bm, answer_b_id=fr)
    )

    assert result.item_ids == tuple(sorted([fr, bm]))
    stored = store.qasets.rows[qaset.id]
    assert [t.other_id for t in stored.answer_translations(fr)] == [bm]
    assert [t.other_id for t in stored.answer_translations(bm)] == [fr]


async def test_link_answers_validations(store: InMemoryStore) -> None:
    qaset = await _qaset(store)
    fr, bm = _answer(qaset, FR), _answer(qaset, BM)
    with pytest.raises(SelfLinkError):
        await _link_answers(store, qaset.id, fr, fr)
    with pytest.raises(AnswerNotFoundError):
        await _link_answers(store, qaset.id, fr, uuid4())
    with pytest.raises(QASetNotFoundError):
        await _link_answers(store, uuid4(), fr, bm)
    await _link_answers(store, qaset.id, fr, bm)
    with pytest.raises(LinkAlreadyExistsError):
        await _link_answers(store, qaset.id, bm, fr)
    assert len(store.qasets.rows[qaset.id].answer_links) == 1


async def test_link_variants_validations_and_free_graph(store: InMemoryStore) -> None:
    qaset = await _qaset(store)
    fr, bm_one, bm_two = _variant(qaset, FR), _variant(qaset, BM, 0), _variant(qaset, BM, 1)
    link = LinkVariantsHandler(store.qasets)

    await link(LinkVariantsCommand(qaset_id=qaset.id, variant_a_id=fr, variant_b_id=bm_one))
    await link(LinkVariantsCommand(qaset_id=qaset.id, variant_a_id=bm_two, variant_b_id=fr))

    with pytest.raises(SameLanguageError):
        await link(LinkVariantsCommand(qaset_id=qaset.id, variant_a_id=bm_one, variant_b_id=bm_two))
    with pytest.raises(QuestionVariantNotFoundError):
        await link(LinkVariantsCommand(qaset_id=qaset.id, variant_a_id=fr, variant_b_id=uuid4()))
    stored = store.qasets.rows[qaset.id]
    assert {t.other_id for t in stored.variant_translations(fr)} == {bm_one, bm_two}


async def test_unlink_removes_only_the_one_link(store: InMemoryStore) -> None:
    qaset = await _qaset(store)
    fr, bm, en = _answer(qaset, FR), _answer(qaset, BM), _answer(qaset, EN)
    removed = await _link_answers(store, qaset.id, fr, bm)
    kept = await _link_answers(store, qaset.id, fr, en)

    await UnlinkAnswersHandler(store.qasets)(UnlinkAnswersCommand(qaset.id, removed))

    assert [link.id for link in store.qasets.rows[qaset.id].answer_links] == [kept]
    with pytest.raises(TranslationLinkNotFoundError):
        await UnlinkAnswersHandler(store.qasets)(UnlinkAnswersCommand(qaset.id, removed))


async def test_unlink_variants(store: InMemoryStore) -> None:
    qaset = await _qaset(store)
    result = await LinkVariantsHandler(store.qasets)(
        LinkVariantsCommand(
            qaset_id=qaset.id,
            variant_a_id=_variant(qaset, FR),
            variant_b_id=_variant(qaset, BM),
        )
    )
    unlink = UnlinkVariantsHandler(store.qasets)
    # An answer link id is not a variant link id.
    answer_link = await _link_answers(store, qaset.id, _answer(qaset, FR), _answer(qaset, BM))
    with pytest.raises(TranslationLinkNotFoundError):
        await unlink(UnlinkVariantsCommand(qaset.id, answer_link))

    await unlink(UnlinkVariantsCommand(qaset.id, result.id))

    assert store.qasets.rows[qaset.id].variant_links == ()
    assert len(store.qasets.rows[qaset.id].answer_links) == 1
