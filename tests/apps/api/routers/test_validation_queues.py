from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.application.validation_queues import (
    MAX_QUEUE_LIMIT,
    AudioQueueItem,
    ClinicalQueueItem,
    NamedRef,
    QueueContext,
    QueueFilter,
    QueuePage,
    QueueState,
    SourceText,
    TranslationQueueItem,
)
from qa_authoring.domain.model.permission import Permission
from tests.fakes import admin_client, in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from tests.fakes import InMemoryStore

CONTEXT = QueueContext(
    NamedRef(uuid4(), "Muso"), NamedRef(uuid4(), "Malaria"), NamedRef(uuid4(), "Fever")
)
QASET, ITEM, SOURCE, AUDIO, NEXT = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()


def _context() -> dict[str, Any]:
    return {
        "project": {"id": str(CONTEXT.project.id), "name": "Muso"},
        "protocol": {"id": str(CONTEXT.protocol.id), "name": "Malaria"},
        "theme": {"id": str(CONTEXT.theme.id), "name": "Fever"},
    }


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryStore]]:
    container, store = in_memory_container()
    queues = store.validation_queues
    queues.pages["clinical"] = QueuePage(
        (ClinicalQueueItem(QASET, CONTEXT, "fr", "A1", ("V1a", "V1b"), "pending"),), NEXT, 3
    )
    queues.pages["translation"] = QueuePage(
        (
            TranslationQueueItem(
                "variant",
                ITEM,
                QASET,
                CONTEXT,
                "bm",
                "BV1",
                (SourceText(SOURCE, "V1a"),),
                None,
                "rejected",
            ),
        ),
        None,
        1,
    )
    queues.pages["audio"] = QueuePage(
        (AudioQueueItem(AUDIO, "answer", ITEM, QASET, CONTEXT, "bm", "B1", "pending"),), None, 1
    )
    with admin_client(container, store) as client:
        yield client, store


def _ok(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_clinical_queue_shape_and_default_filter(setup: tuple[TestClient, InMemoryStore]) -> None:
    client, store = setup
    body = _ok(client.get("/validation-queues/clinical"))
    assert body == {
        "items": [
            {
                "qaset_id": str(QASET),
                **_context(),
                "base_language_code": "fr",
                "answer_text": "A1",
                "variant_texts": ["V1a", "V1b"],
                "state": "pending",
            }
        ],
        "next_cursor": str(NEXT),
        "total": 3,
    }
    assert store.validation_queues.calls == [("clinical", QueueFilter())]


def test_translation_queue_shape(setup: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = setup
    [item] = _ok(client.get("/validation-queues/translation"))["items"]
    assert item == {
        "kind": "variant",
        "item_id": str(ITEM),
        "qaset_id": str(QASET),
        **_context(),
        "language_code": "bm",
        "text": "BV1",
        "sources": [{"item_id": str(SOURCE), "text": "V1a"}],
        "fallback_base_answer_text": None,
        "state": "rejected",
    }


def test_audio_queue_shape(setup: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = setup
    body = _ok(client.get("/validation-queues/audio"))
    assert body["next_cursor"] is None and body["total"] == 1
    assert body["items"] == [
        {
            "audio_id": str(AUDIO),
            "item_kind": "answer",
            "item_id": str(ITEM),
            "qaset_id": str(QASET),
            **_context(),
            "language_code": "bm",
            "text": "B1",
            "state": "pending",
        }
    ]


def test_filters_are_passed_through_and_the_limit_capped(
    setup: tuple[TestClient, InMemoryStore],
) -> None:
    client, store = setup
    project, theme, cursor = uuid4(), uuid4(), uuid4()
    params = {
        "project_id": str(project),
        "theme_id": str(theme),
        "state": "all",
        "limit": "5000",
        "cursor": str(cursor),
    }
    _ok(client.get("/validation-queues/audio", params=params))
    assert store.validation_queues.calls == [
        ("audio", QueueFilter(project, theme, QueueState.ALL, MAX_QUEUE_LIMIT, cursor))
    ]


@pytest.mark.parametrize("queue", ["clinical", "translation", "audio"])
@pytest.mark.parametrize(
    "params", [{"state": "approved"}, {"state": "PENDING"}, {"cursor": "nope"}, {"limit": "0"}]
)
def test_invalid_filters(
    setup: tuple[TestClient, InMemoryStore], queue: str, params: dict[str, str]
) -> None:
    client, store = setup
    response = client.get(f"/validation-queues/{queue}", params=params)
    assert response.status_code == 422, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == "invalid_queue_filter"
    assert store.validation_queues.calls == []


@pytest.mark.parametrize(
    ("queue", "permission"),
    [
        ("clinical", Permission.VALIDATE_CLINICAL),
        ("translation", Permission.VALIDATE_TRANSLATION),
        ("audio", Permission.VALIDATE_AUDIO),
    ],
)
def test_each_queue_needs_its_permission(
    setup: tuple[TestClient, InMemoryStore], queue: str, permission: Permission
) -> None:
    client, store = setup
    seed_user(store, "without@example.org", *[p for p in Permission if p is not permission])
    seed_user(store, "with@example.org", permission)

    denied = client.get(
        f"/validation-queues/{queue}", headers={"X-Dev-User": "without@example.org"}
    )
    allowed = client.get(f"/validation-queues/{queue}", headers={"X-Dev-User": "with@example.org"})

    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
    assert allowed.status_code == 200, allowed.text
