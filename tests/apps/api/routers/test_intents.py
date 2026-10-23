from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from tests.fakes import in_memory_container

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def client() -> Iterator[TestClient]:
    container, _ = in_memory_container()
    with TestClient(create_app(container=container)) as client:
        yield client


def _ok(response: Any, status: int = 201) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


def _error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code


def _intent(client: TestClient, text: str) -> str:
    return str(_ok(client.post("/intents", json={"text": text}))["id"])


@pytest.fixture
def variant(client: TestClient) -> tuple[str, str]:
    fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
    project = _ok(client.post("/projects", json={"name": "P", "base_language_id": fr}))["id"]
    protocol = _ok(client.post(f"/projects/{project}/protocols", json={"name": "Pr"}))["id"]
    theme = _ok(client.post(f"/protocols/{protocol}/themes", json={"name": "T"}))["id"]
    qaset = _ok(
        client.post(f"/themes/{theme}/qasets", json={"language_id": fr, "answer_text": "a"})
    )["id"]
    variant = _ok(client.post(f"/qasets/{qaset}/languages/{fr}/variants", json={"text": "q"}))
    return str(qaset), str(variant["id"])


def _read_variant(client: TestClient, qaset_id: str) -> dict[str, Any]:
    body = _ok(client.get(f"/qasets/{qaset_id}"), 200)
    [variant] = body["languages"][0]["variants"]
    found: dict[str, Any] = variant
    return found


# --- catalogue ---


def test_register_is_idempotent_on_normalized_text(client: TestClient) -> None:
    created = _ok(client.post("/intents", json={"text": " Dosage "}))
    assert created == {"id": created["id"], "text": "Dosage"}

    again = _ok(client.post("/intents", json={"text": "DOSAGE"}), 200)

    assert again == created
    assert _ok(client.get("/intents"), 200) == {"items": [created]}


def test_register_validation(client: TestClient) -> None:
    _error(client.post("/intents", json={"text": "  "}), 422, "invalid_text")
    _error(client.post("/intents", json={}), 422, "invalid_request")


def test_list_with_prefix_filter(client: TestClient) -> None:
    for text in ("Side effects", "Dosage for children", "dosage for adults"):
        _intent(client, text)

    items = _ok(client.get("/intents", params={"q": "DOSAGE "}), 200)["items"]

    assert [item["text"] for item in items] == ["dosage for adults", "Dosage for children"]
    assert _ok(client.get("/intents", params={"q": "zzz"}), 200) == {"items": []}


def test_get_and_delete_intent(client: TestClient) -> None:
    intent_id = _intent(client, "Dosage")
    assert _ok(client.get(f"/intents/{intent_id}"), 200) == {"id": intent_id, "text": "Dosage"}

    assert client.delete(f"/intents/{intent_id}").status_code == 204
    _error(client.get(f"/intents/{intent_id}"), 404, "intent_not_found")
    _error(client.delete(f"/intents/{intent_id}"), 404, "intent_not_found")
    assert client.get("/intents/not-a-uuid").status_code == 422


def test_delete_attached_intent_is_409(client: TestClient, variant: tuple[str, str]) -> None:
    qaset_id, variant_id = variant
    intent_id = _intent(client, "Dosage")
    _ok(
        client.post(
            f"/qasets/{qaset_id}/variants/{variant_id}/intents", json={"intent_id": intent_id}
        )
    )
    _error(client.delete(f"/intents/{intent_id}"), 409, "intent_in_use")


# --- attachment ---


def test_attach_and_detach(client: TestClient, variant: tuple[str, str]) -> None:
    qaset_id, variant_id = variant
    first, second = _intent(client, "Side effects"), _intent(client, "Dosage")
    url = f"/qasets/{qaset_id}/variants/{variant_id}/intents"

    attached = _ok(client.post(url, json={"intent_id": first}))
    assert attached["id"] == variant_id
    assert attached["intents"] == [{"intent_id": first, "text": "Side effects"}]

    again = _ok(client.post(url, json={"intent_id": first}), 200)
    assert again == attached

    _ok(client.post(url, json={"intent_id": second}))
    assert _read_variant(client, qaset_id)["intents"] == [
        {"intent_id": first, "text": "Side effects"},
        {"intent_id": second, "text": "Dosage"},
    ]

    assert client.delete(f"{url}/{first}").status_code == 204
    assert _read_variant(client, qaset_id)["intents"] == [{"intent_id": second, "text": "Dosage"}]
    _error(client.delete(f"{url}/{first}"), 404, "intent_not_attached")


def test_attach_errors(client: TestClient, variant: tuple[str, str]) -> None:
    qaset_id, variant_id = variant
    intent_id = _intent(client, "Dosage")
    _error(
        client.post(
            f"/qasets/{qaset_id}/variants/{variant_id}/intents", json={"intent_id": str(uuid4())}
        ),
        404,
        "intent_not_found",
    )
    _error(
        client.post(
            f"/qasets/{qaset_id}/variants/{uuid4()}/intents", json={"intent_id": intent_id}
        ),
        404,
        "variant_not_found",
    )
    _error(
        client.post(
            f"/qasets/{uuid4()}/variants/{variant_id}/intents", json={"intent_id": intent_id}
        ),
        404,
        "qaset_not_found",
    )
    _error(
        client.post(f"/qasets/{qaset_id}/variants/{variant_id}/intents", json={}),
        422,
        "invalid_request",
    )
    _error(
        client.delete(f"/qasets/{qaset_id}/variants/{uuid4()}/intents/{intent_id}"),
        404,
        "variant_not_found",
    )


def test_intent_text_follows_the_catalogue(client: TestClient, variant: tuple[str, str]) -> None:
    qaset_id, variant_id = variant
    intent_id = _intent(client, "Dosage")
    _ok(
        client.post(
            f"/qasets/{qaset_id}/variants/{variant_id}/intents", json={"intent_id": intent_id}
        )
    )

    patched = _ok(
        client.patch(f"/qasets/{qaset_id}/variants/{variant_id}", json={"text": "q2"}), 200
    )

    assert patched["intents"] == [{"intent_id": intent_id, "text": "Dosage"}]
