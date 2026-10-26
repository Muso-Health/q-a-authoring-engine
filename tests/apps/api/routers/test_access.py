from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.domain.model.permission import Permission
from tests.fakes import ADMIN_EMAIL, admin_client, in_memory_container

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    container, store = in_memory_container()
    with admin_client(container, store) as client:
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


def test_permissions_lists_the_catalogue(client: TestClient) -> None:
    assert _ok(client.get("/permissions"), 200) == {"items": sorted(p.value for p in Permission)}


def test_me(client: TestClient) -> None:
    me = _ok(client.get("/me"), 200)
    # Never the subject (oid).
    assert set(me) == {"id", "email", "display_name", "permissions", "assignments", "grants"}
    assert me["email"] == ADMIN_EMAIL
    assert me["permissions"] == sorted(p.value for p in Permission)
    [assignment] = me["assignments"]
    assert (assignment["project"], assignment["language"]) == (None, None)
    assert {g["permission"] for g in me["grants"]} == {p.value for p in Permission}
    assert all(g["project_id"] is None and g["language_id"] is None for g in me["grants"])


def test_role_crud(client: TestClient) -> None:
    created = _ok(
        client.post("/roles", json={"name": " Author ", "permissions": ["author_qasets"]})
    )
    assert created == {"id": created["id"], "name": "Author", "permissions": ["author_qasets"]}
    url = f"/roles/{created['id']}"
    assert _ok(client.get(url), 200) == created
    assert created in _ok(client.get("/roles"), 200)["items"]

    patched = _ok(client.patch(url, json={"permissions": ["manage_audio", "author_qasets"]}), 200)
    assert patched["permissions"] == ["author_qasets", "manage_audio"]
    assert _ok(client.patch(url, json={"name": "Writer"}), 200)["name"] == "Writer"

    assert client.delete(url).status_code == 204
    _error(client.get(url), 404, "role_not_found")


def test_role_errors(client: TestClient) -> None:
    role = _ok(client.post("/roles", json={"name": "Author", "permissions": []}))
    _error(
        client.post("/roles", json={"name": "AUTHOR", "permissions": []}), 409, "role_name_exists"
    )
    _error(
        client.post("/roles", json={"name": "Pilot", "permissions": ["fly"]}),
        422,
        "unknown_permission",
    )
    _error(client.post("/roles", json={"name": " ", "permissions": []}), 422, "invalid_name")
    _error(client.patch(f"/roles/{uuid4()}", json={"name": "x"}), 404, "role_not_found")
    _error(client.delete(f"/roles/{uuid4()}"), 404, "role_not_found")
    _error(
        client.patch(f"/roles/{role['id']}", json={"permissions": ["nope"]}),
        422,
        "unknown_permission",
    )


def test_user_crud_and_role_assignment(client: TestClient) -> None:
    role = _ok(client.post("/roles", json={"name": "Author", "permissions": ["author_qasets"]}))
    created = _ok(client.post("/users", json={"email": "Ada@Example.org", "display_name": "Ada"}))
    assert created == {
        "id": created["id"],
        "email": "ada@example.org",
        "display_name": "Ada",
        "is_active": True,
        "assignments": [],
        "grants": [],
    }
    url = f"/users/{created['id']}"
    assert _ok(client.get(url), 200) == created
    emails = [u["email"] for u in _ok(client.get("/users"), 200)["items"]]
    assert emails == ["ada@example.org", ADMIN_EMAIL]

    assigned = _ok(client.post(f"{url}/assignments", json={"role_id": role["id"]}))
    [assignment] = assigned["assignments"]
    assert assignment == {
        "id": assignment["id"],
        "role": {"id": role["id"], "name": "Author"},
        "project": None,
        "language": None,
    }
    assert assigned["grants"] == [
        {"permission": "author_qasets", "project_id": None, "language_id": None}
    ]
    assert _ok(client.post(f"{url}/assignments", json={"role_id": role["id"]}), 200) == assigned
    _error(client.delete(f"/roles/{role['id']}"), 409, "role_in_use")

    patched = _ok(client.patch(url, json={"display_name": "Countess", "is_active": False}), 200)
    assert (patched["display_name"], patched["is_active"]) == ("Countess", False)

    assert client.delete(f"{url}/assignments/{assignment['id']}").status_code == 204
    assert _ok(client.get(url), 200)["assignments"] == []
    _error(client.delete(f"{url}/assignments/{assignment['id']}"), 404, "assignment_not_found")


def test_user_errors(client: TestClient) -> None:
    _ok(client.post("/users", json={"email": "ada@example.org", "display_name": "Ada"}))
    _error(
        client.post("/users", json={"email": "ADA@example.org", "display_name": "A"}),
        409,
        "email_already_exists",
    )
    _error(client.post("/users", json={"email": "nope", "display_name": "A"}), 422, "invalid_email")
    _error(client.get(f"/users/{uuid4()}"), 404, "user_not_found")
    _error(client.patch(f"/users/{uuid4()}", json={"is_active": True}), 404, "user_not_found")
    _error(
        client.post(f"/users/{uuid4()}/assignments", json={"role_id": str(uuid4())}),
        404,
        "user_not_found",
    )
    _error(client.post("/users", json={"email": "x@example.org"}), 422, "invalid_request")


def test_the_identity_subject_is_never_exposed(client: TestClient) -> None:
    created = _ok(client.post("/users", json={"email": "a@example.org", "display_name": "A"}))
    bodies = [
        _ok(client.get("/me"), 200),
        created,
        _ok(client.get(f"/users/{created['id']}"), 200),
        *_ok(client.get("/users"), 200)["items"],
    ]
    assert all("subject" not in body and "oid" not in body for body in bodies)
