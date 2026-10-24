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


def _category(client: TestClient, name: str) -> str:
    return str(_ok(client.post("/categories", json={"name": name}))["id"])


@pytest.fixture
def qaset_id(client: TestClient) -> str:
    fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
    project = _ok(client.post("/projects", json={"name": "P", "base_language_id": fr}))["id"]
    protocol = _ok(client.post(f"/projects/{project}/protocols", json={"name": "Pr"}))["id"]
    theme = _ok(client.post(f"/protocols/{protocol}/themes", json={"name": "T"}))["id"]
    qaset = _ok(
        client.post(f"/themes/{theme}/qasets", json={"language_id": fr, "answer_text": "a"})
    )
    _ok(client.post(f"/qasets/{qaset['id']}/languages/{fr}/variants", json={"text": "q"}))
    return str(qaset["id"])


# --- catalogue ---


def test_register_is_idempotent_on_normalized_name(client: TestClient) -> None:
    created = _ok(client.post("/categories", json={"name": " Malaria "}))
    assert created == {"id": created["id"], "name": "Malaria"}

    again = _ok(client.post("/categories", json={"name": "MALARIA"}), 200)

    assert again == created
    assert _ok(client.get("/categories"), 200) == {"items": [created]}


def test_register_validation(client: TestClient) -> None:
    _error(client.post("/categories", json={"name": "  "}), 422, "invalid_name")
    _error(client.post("/categories", json={}), 422, "invalid_request")


def test_list_with_prefix_filter(client: TestClient) -> None:
    for name in ("Nutrition", "Child health", "child hygiene"):
        _category(client, name)

    items = _ok(client.get("/categories", params={"q": "CHILD "}), 200)["items"]

    assert [item["name"] for item in items] == ["Child health", "child hygiene"]
    assert _ok(client.get("/categories", params={"q": "zzz"}), 200) == {"items": []}


def test_get_and_delete_category(client: TestClient) -> None:
    category_id = _category(client, "Malaria")
    assert _ok(client.get(f"/categories/{category_id}"), 200) == {
        "id": category_id,
        "name": "Malaria",
    }

    assert client.delete(f"/categories/{category_id}").status_code == 204
    _error(client.get(f"/categories/{category_id}"), 404, "category_not_found")
    _error(client.delete(f"/categories/{category_id}"), 404, "category_not_found")
    assert client.get("/categories/not-a-uuid").status_code == 422


def test_delete_attached_category_is_409(client: TestClient, qaset_id: str) -> None:
    category_id = _category(client, "Malaria")
    _ok(client.post(f"/qasets/{qaset_id}/categories", json={"category_id": category_id}))
    _error(client.delete(f"/categories/{category_id}"), 409, "category_in_use")


# --- attachment ---


def test_add_and_remove_categories(client: TestClient, qaset_id: str) -> None:
    first, second = _category(client, "Nutrition"), _category(client, "Malaria")
    url = f"/qasets/{qaset_id}/categories"
    before = _ok(client.get(f"/qasets/{qaset_id}"), 200)
    assert before["categories"] == []

    added = _ok(client.post(url, json={"category_id": first}))
    assert added["id"] == qaset_id
    assert added["categories"] == [{"category_id": first, "name": "Nutrition"}]
    assert added["languages"] == before["languages"]

    again = _ok(client.post(url, json={"category_id": first}), 200)
    assert again == added

    _ok(client.post(url, json={"category_id": second}))
    assert _ok(client.get(f"/qasets/{qaset_id}"), 200)["categories"] == [
        {"category_id": first, "name": "Nutrition"},
        {"category_id": second, "name": "Malaria"},
    ]

    assert client.delete(f"{url}/{first}").status_code == 204
    assert _ok(client.get(f"/qasets/{qaset_id}"), 200)["categories"] == [
        {"category_id": second, "name": "Malaria"}
    ]
    _error(client.delete(f"{url}/{first}"), 404, "category_not_attached")


def test_attach_errors(client: TestClient, qaset_id: str) -> None:
    category_id = _category(client, "Malaria")
    _error(
        client.post(f"/qasets/{qaset_id}/categories", json={"category_id": str(uuid4())}),
        404,
        "category_not_found",
    )
    _error(
        client.post(f"/qasets/{uuid4()}/categories", json={"category_id": category_id}),
        404,
        "qaset_not_found",
    )
    _error(client.post(f"/qasets/{qaset_id}/categories", json={}), 422, "invalid_request")
    _error(client.delete(f"/qasets/{uuid4()}/categories/{category_id}"), 404, "qaset_not_found")
