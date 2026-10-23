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


def _language(client: TestClient, code: str = "fr") -> str:
    return str(_ok(client.post("/languages", json={"code": code, "name": code}))["id"])


def _project(client: TestClient, name: str = "Malaria", language_id: str | None = None) -> str:
    payload = {"name": name, "base_language_id": language_id or _language(client)}
    return str(_ok(client.post("/projects", json=payload))["id"])


def _protocol(client: TestClient, project_id: str, name: str = "Triage") -> str:
    return str(_ok(client.post(f"/projects/{project_id}/protocols", json={"name": name}))["id"])


def _theme(client: TestClient, protocol_id: str, name: str = "Fever") -> str:
    return str(_ok(client.post(f"/protocols/{protocol_id}/themes", json={"name": name}))["id"])


def _error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code


# --- /projects ---


def test_project_crud(client: TestClient) -> None:
    language_id = _language(client)
    created = _ok(
        client.post(
            "/projects",
            json={"name": " Malaria ", "description": "CHW", "base_language_id": language_id},
        )
    )
    assert created == {
        "id": created["id"],
        "name": "Malaria",
        "description": "CHW",
        "base_language_id": language_id,
    }
    url = f"/projects/{created['id']}"

    assert _ok(client.get(url), 200) == created
    assert _ok(client.get("/projects"), 200) == {"items": [created]}

    renamed = _ok(client.patch(url, json={"name": "Malaria v2"}), 200)
    assert (renamed["name"], renamed["description"]) == ("Malaria v2", "CHW")
    cleared = _ok(client.patch(url, json={"description": None}), 200)
    assert (cleared["name"], cleared["description"]) == ("Malaria v2", None)
    assert cleared["base_language_id"] == language_id

    response = client.delete(url)
    assert response.status_code == 204
    assert response.content == b""
    _error(client.get(url), 404, "project_not_found")


def test_create_project_with_unknown_base_language_is_422(client: TestClient) -> None:
    response = client.post("/projects", json={"name": "M", "base_language_id": str(uuid4())})
    _error(response, 422, "unknown_base_language")


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"name": " "}, "invalid_name"),
        ({}, "invalid_request"),
        ({"name": "M", "base_language_id": "nope"}, "invalid_request"),
        ({"name": "M", "extra": 1}, "invalid_request"),
    ],
)
def test_create_project_validation_is_422(
    client: TestClient, payload: dict[str, Any], code: str
) -> None:
    body = {"base_language_id": _language(client), **payload}
    _error(client.post("/projects", json=body), 422, code)


def test_patch_project_base_language_is_422(client: TestClient) -> None:
    project_id = _project(client)
    other = _language(client, "en")
    response = client.patch(f"/projects/{project_id}", json={"base_language_id": other})
    _error(response, 422, "invalid_request")
    assert _ok(client.get(f"/projects/{project_id}"), 200)["base_language_id"] != other


@pytest.mark.parametrize("payload", [{"name": " "}, {"name": None}])
def test_patch_project_invalid_name_is_422(client: TestClient, payload: dict[str, Any]) -> None:
    response = client.patch(f"/projects/{_project(client)}", json=payload)
    assert response.status_code == 422


def test_project_unknown_id_is_404(client: TestClient) -> None:
    url = f"/projects/{uuid4()}"
    _error(client.get(url), 404, "project_not_found")
    _error(client.patch(url, json={"name": "X"}), 404, "project_not_found")
    _error(client.delete(url), 404, "project_not_found")


def test_delete_project_with_protocols_is_409(client: TestClient) -> None:
    project_id = _project(client)
    _protocol(client, project_id)
    _error(client.delete(f"/projects/{project_id}"), 409, "project_has_protocols")


def test_delete_language_used_as_base_language_is_409(client: TestClient) -> None:
    language_id = _language(client)
    _project(client, language_id=language_id)
    _error(client.delete(f"/languages/{language_id}"), 409, "language_in_use")
    assert client.get(f"/languages/{language_id}").status_code == 200


# --- protocols ---


def test_protocol_crud(client: TestClient) -> None:
    project_id = _project(client)
    created = _ok(
        client.post(
            f"/projects/{project_id}/protocols", json={"name": "Triage", "description": "d"}
        )
    )
    assert created == {
        "id": created["id"],
        "project_id": project_id,
        "name": "Triage",
        "description": "d",
    }
    url = f"/protocols/{created['id']}"

    assert _ok(client.get(url), 200) == created
    updated = _ok(client.patch(url, json={"name": "Triage v2", "description": None}), 200)
    assert (updated["name"], updated["description"]) == ("Triage v2", None)

    assert client.delete(url).status_code == 204
    _error(client.get(url), 404, "protocol_not_found")


def test_list_protocols_by_project(client: TestClient) -> None:
    project_a = _project(client, "A")
    project_b = _project(client, "B", language_id=_language(client, "en"))
    _protocol(client, project_a, "Zeta")
    _protocol(client, project_a, "Alpha")
    _protocol(client, project_b, "Other")

    items = _ok(client.get(f"/projects/{project_a}/protocols"), 200)["items"]

    assert [item["name"] for item in items] == ["Alpha", "Zeta"]


def test_protocols_under_unknown_project_are_404(client: TestClient) -> None:
    url = f"/projects/{uuid4()}/protocols"
    _error(client.post(url, json={"name": "Triage"}), 404, "project_not_found")
    _error(client.get(url), 404, "project_not_found")


def test_protocol_unknown_id_is_404(client: TestClient) -> None:
    url = f"/protocols/{uuid4()}"
    _error(client.get(url), 404, "protocol_not_found")
    _error(client.patch(url, json={"name": "X"}), 404, "protocol_not_found")
    _error(client.delete(url), 404, "protocol_not_found")


def test_protocol_validation_is_422(client: TestClient) -> None:
    project_id = _project(client)
    _error(client.post(f"/projects/{project_id}/protocols", json={"name": ""}), 422, "invalid_name")
    protocol_id = _protocol(client, project_id)
    _error(
        client.patch(f"/protocols/{protocol_id}", json={"project_id": str(uuid4())}),
        422,
        "invalid_request",
    )


def test_delete_protocol_with_themes_is_409(client: TestClient) -> None:
    protocol_id = _protocol(client, _project(client))
    _theme(client, protocol_id)
    _error(client.delete(f"/protocols/{protocol_id}"), 409, "protocol_has_themes")


# --- themes ---


def test_theme_crud(client: TestClient) -> None:
    protocol_id = _protocol(client, _project(client))
    created = _ok(client.post(f"/protocols/{protocol_id}/themes", json={"name": "Fever"}))
    assert created == {
        "id": created["id"],
        "protocol_id": protocol_id,
        "name": "Fever",
        "description": None,
    }
    url = f"/themes/{created['id']}"

    assert _ok(client.get(url), 200) == created
    updated = _ok(client.patch(url, json={"description": "High temperature"}), 200)
    assert (updated["name"], updated["description"]) == ("Fever", "High temperature")

    assert client.delete(url).status_code == 204
    _error(client.get(url), 404, "theme_not_found")


def test_list_themes_by_protocol(client: TestClient) -> None:
    project_id = _project(client)
    protocol_a = _protocol(client, project_id, "A")
    protocol_b = _protocol(client, project_id, "B")
    _theme(client, protocol_a, "Fever")
    _theme(client, protocol_a, "Cough")
    _theme(client, protocol_b, "Other")

    items = _ok(client.get(f"/protocols/{protocol_a}/themes"), 200)["items"]

    assert [item["name"] for item in items] == ["Cough", "Fever"]


def test_themes_under_unknown_protocol_are_404(client: TestClient) -> None:
    url = f"/protocols/{uuid4()}/themes"
    _error(client.post(url, json={"name": "Fever"}), 404, "protocol_not_found")
    _error(client.get(url), 404, "protocol_not_found")


def test_theme_unknown_id_is_404(client: TestClient) -> None:
    url = f"/themes/{uuid4()}"
    _error(client.get(url), 404, "theme_not_found")
    _error(client.patch(url, json={"name": "X"}), 404, "theme_not_found")
    _error(client.delete(url), 404, "theme_not_found")


def test_theme_validation_is_422(client: TestClient) -> None:
    protocol_id = _protocol(client, _project(client))
    _error(
        client.post(f"/protocols/{protocol_id}/themes", json={"name": "  "}), 422, "invalid_name"
    )
    theme_id = _theme(client, protocol_id)
    _error(
        client.patch(f"/themes/{theme_id}", json={"protocol_id": str(uuid4())}),
        422,
        "invalid_request",
    )
    assert client.get("/themes/not-a-uuid").status_code == 422
