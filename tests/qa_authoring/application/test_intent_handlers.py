from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qa_authoring.application.attach_intent.command import AttachIntentCommand
from qa_authoring.application.attach_intent.handler import AttachIntentHandler
from qa_authoring.application.delete_intent.command import DeleteIntentCommand
from qa_authoring.application.delete_intent.handler import DeleteIntentHandler
from qa_authoring.application.detach_intent.command import DetachIntentCommand
from qa_authoring.application.detach_intent.handler import DetachIntentHandler
from qa_authoring.application.get_intent.command import GetIntentQuery
from qa_authoring.application.get_intent.handler import GetIntentHandler
from qa_authoring.application.get_qaset.command import GetQASetQuery
from qa_authoring.application.get_qaset.handler import GetQASetHandler
from qa_authoring.application.intent_errors import IntentInUseError, IntentNotFoundError
from qa_authoring.application.list_intents.command import ListIntentsQuery
from qa_authoring.application.list_intents.handler import ListIntentsHandler
from qa_authoring.application.qaset_errors import QASetNotFoundError
from qa_authoring.application.register_intent.command import RegisterIntentCommand
from qa_authoring.application.register_intent.handler import RegisterIntentHandler
from qa_authoring.domain.model.qaset import (
    IntentNotAttachedError,
    QASet,
    QuestionVariantNotFoundError,
)
from qa_authoring.domain.value_objects.naming import InvalidTextError
from tests.fakes import InMemoryStore, views

FR = uuid4()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


async def _register(store: InMemoryStore, text: str) -> UUID:
    result, _ = await RegisterIntentHandler(store.intents)(RegisterIntentCommand(text))
    return result.id


async def _qaset(store: InMemoryStore) -> tuple[QASet, UUID]:
    qaset = QASet.create(theme_id=uuid4(), language_id=FR, answer_text="a")
    variant = qaset.add_variant(FR, "q")
    await store.qasets.add(qaset)
    return qaset, variant.id


async def _attach(store: InMemoryStore, qaset_id: UUID, variant_id: UUID, intent_id: UUID) -> bool:
    _, created = await AttachIntentHandler(store.qasets, store.intents, views(store))(
        AttachIntentCommand(qaset_id=qaset_id, variant_id=variant_id, intent_id=intent_id)
    )
    return created


# --- catalogue ---


async def test_register_is_get_or_create_on_the_normalized_text(store: InMemoryStore) -> None:
    register = RegisterIntentHandler(store.intents)

    created, was_created = await register(RegisterIntentCommand(" Dosage "))
    again, created_again = await register(RegisterIntentCommand("DOSAGE"))

    assert (created.text, was_created) == ("Dosage", True)
    assert (again, created_again) == (created, False)
    assert len(store.intents.rows) == 1


async def test_register_rejects_blank_text(store: InMemoryStore) -> None:
    with pytest.raises(InvalidTextError):
        await RegisterIntentHandler(store.intents)(RegisterIntentCommand("  "))


async def test_list_filters_by_normalized_prefix(store: InMemoryStore) -> None:
    for text in ("Side effects", "Dosage for children", "dosage for adults", "Prevention"):
        await _register(store, text)
    list_intents = ListIntentsHandler(store.intents)

    everything = await list_intents(ListIntentsQuery())
    dosage = await list_intents(ListIntentsQuery(prefix="  DOSAGE  for"))

    assert [i.text for i in everything] == [
        "dosage for adults",
        "Dosage for children",
        "Prevention",
        "Side effects",
    ]
    assert [i.text for i in dosage] == ["dosage for adults", "Dosage for children"]


async def test_get_intent(store: InMemoryStore) -> None:
    intent_id = await _register(store, "Dosage")
    assert (await GetIntentHandler(store.intents)(GetIntentQuery(intent_id))).text == "Dosage"
    with pytest.raises(IntentNotFoundError):
        await GetIntentHandler(store.intents)(GetIntentQuery(uuid4()))


async def test_delete_intent_is_guarded_while_attached(store: InMemoryStore) -> None:
    intent_id = await _register(store, "Dosage")
    qaset, variant_id = await _qaset(store)
    await _attach(store, qaset.id, variant_id, intent_id)
    delete = DeleteIntentHandler(store.intents, store.qasets)

    with pytest.raises(IntentInUseError):
        await delete(DeleteIntentCommand(intent_id))
    assert intent_id in store.intents.rows

    await DetachIntentHandler(store.qasets)(
        DetachIntentCommand(qaset_id=qaset.id, variant_id=variant_id, intent_id=intent_id)
    )
    await delete(DeleteIntentCommand(intent_id))
    assert intent_id not in store.intents.rows
    with pytest.raises(IntentNotFoundError):
        await delete(DeleteIntentCommand(intent_id))


# --- attachment ---


async def test_attach_validates_variant_and_intent(store: InMemoryStore) -> None:
    intent_id = await _register(store, "Dosage")
    qaset, variant_id = await _qaset(store)
    with pytest.raises(IntentNotFoundError):
        await _attach(store, qaset.id, variant_id, uuid4())
    with pytest.raises(QuestionVariantNotFoundError):
        await _attach(store, qaset.id, uuid4(), intent_id)
    with pytest.raises(QASetNotFoundError):
        await _attach(store, uuid4(), variant_id, intent_id)


async def test_attach_twice_is_idempotent(store: InMemoryStore) -> None:
    intent_id = await _register(store, "Dosage")
    qaset, variant_id = await _qaset(store)

    assert await _attach(store, qaset.id, variant_id, intent_id) is True
    assert await _attach(store, qaset.id, variant_id, intent_id) is False

    assert store.qasets.rows[qaset.id].variants[0].intent_ids == (intent_id,)


async def test_attach_returns_the_variant_with_its_intents(store: InMemoryStore) -> None:
    intent_id = await _register(store, "Dosage")
    qaset, variant_id = await _qaset(store)
    result, _ = await AttachIntentHandler(store.qasets, store.intents, views(store))(
        AttachIntentCommand(qaset_id=qaset.id, variant_id=variant_id, intent_id=intent_id)
    )
    assert result.id == variant_id
    assert [(i.intent_id, i.text) for i in result.intents] == [(intent_id, "Dosage")]


async def test_detach_removes_only_that_attachment(store: InMemoryStore) -> None:
    kept, removed = await _register(store, "Dosage"), await _register(store, "Side effects")
    qaset, variant_id = await _qaset(store)
    await _attach(store, qaset.id, variant_id, kept)
    await _attach(store, qaset.id, variant_id, removed)
    detach = DetachIntentHandler(store.qasets)

    await detach(DetachIntentCommand(qaset_id=qaset.id, variant_id=variant_id, intent_id=removed))

    assert store.qasets.rows[qaset.id].variants[0].intent_ids == (kept,)
    with pytest.raises(IntentNotAttachedError):
        await detach(
            DetachIntentCommand(qaset_id=qaset.id, variant_id=variant_id, intent_id=removed)
        )


async def test_get_qaset_shows_intents_in_attachment_order(store: InMemoryStore) -> None:
    first, second = await _register(store, "Side effects"), await _register(store, "Dosage")
    qaset, variant_id = await _qaset(store)
    await _attach(store, qaset.id, variant_id, first)
    await _attach(store, qaset.id, variant_id, second)

    result = await GetQASetHandler(store.qasets, views(store))(GetQASetQuery(qaset.id))

    [variant] = result.languages[0].variants
    assert [(i.intent_id, i.text) for i in variant.intents] == [
        (first, "Side effects"),
        (second, "Dosage"),
    ]
