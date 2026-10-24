from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from tests.fakes import admin_client, in_memory_container

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    container, store = in_memory_container()
    with admin_client(container, store) as client:
        yield client


def _create(client: TestClient, code: str = "fr", name: str = "French") -> dict[str, Any]:
    response = client.post("/languages", json={"code": code, "name": name})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_post_registers_a_language(client: TestClient) -> None:
    body = _create(client, "bm_fr", " Bambara (French) ")
    assert set(body) == {"id", "code", "name"}
    assert body["code"] == "bm_fr"
    assert body["name"] == "Bambara (French)"


def test_post_duplicate_code_is_409(client: TestClient) -> None:
    _create(client, "fr")
    response = client.post("/languages", json={"code": "fr", "name": "Français"})
    assert response.status_code == 409
    assert response.json()["code"] == "language_code_already_exists"
    assert set(response.json()) == {"code", "message", "details"}


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        ({"code": "fr-FR", "name": "French"}, "invalid_language_code"),
        ({"code": "FR", "name": "French"}, "invalid_language_code"),
        ({"code": "fr", "name": "   "}, "invalid_language_name"),
        ({"code": "fr"}, "invalid_request"),
    ],
)
def test_post_invalid_body_is_422(
    client: TestClient, payload: dict[str, str], error_code: str
) -> None:
    response = client.post("/languages", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == error_code


def test_get_list_returns_languages_ordered_by_code(client: TestClient) -> None:
    _create(client, "fr", "French")
    _create(client, "bm", "Bambara")

    response = client.get("/languages")

    assert response.status_code == 200
    assert [item["code"] for item in response.json()["items"]] == ["bm", "fr"]


def test_get_list_is_empty_initially(client: TestClient) -> None:
    assert client.get("/languages").json() == {"items": []}


def test_get_by_id_returns_the_language(client: TestClient) -> None:
    created = _create(client)
    response = client.get(f"/languages/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_id_is_404(client: TestClient) -> None:
    response = client.get(f"/languages/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "language_not_found"


def test_get_malformed_id_is_422(client: TestClient) -> None:
    assert client.get("/languages/not-a-uuid").status_code == 422


def test_patch_renames_and_keeps_the_code(client: TestClient) -> None:
    created = _create(client, "fr", "French")

    response = client.patch(f"/languages/{created['id']}", json={"name": "Français"})

    assert response.status_code == 200
    assert response.json() == {"id": created["id"], "code": "fr", "name": "Français"}
    assert client.get(f"/languages/{created['id']}").json()["name"] == "Français"


def test_patch_rejects_a_code_change(client: TestClient) -> None:
    created = _create(client, "fr", "French")

    response = client.patch(f"/languages/{created['id']}", json={"code": "en", "name": "English"})

    assert response.status_code == 422
    assert client.get(f"/languages/{created['id']}").json()["code"] == "fr"


def test_patch_blank_name_is_422(client: TestClient) -> None:
    created = _create(client)
    response = client.patch(f"/languages/{created['id']}", json={"name": " "})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_language_name"


def test_patch_unknown_id_is_404(client: TestClient) -> None:
    response = client.patch(f"/languages/{uuid4()}", json={"name": "X"})
    assert response.status_code == 404
    assert response.json()["code"] == "language_not_found"


def test_delete_removes_the_language(client: TestClient) -> None:
    created = _create(client)

    response = client.delete(f"/languages/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/languages/{created['id']}").status_code == 404


def test_delete_unknown_id_is_404(client: TestClient) -> None:
    response = client.delete(f"/languages/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "language_not_found"
