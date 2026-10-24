from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.auth import PermissionGuard, current_user
from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.user import User
from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from tests.fakes import in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.dependencies.models import Dependant

    from tests.fakes import InMemoryStore


@pytest.fixture
def world() -> Iterator[tuple[TestClient, InMemoryStore]]:
    container, store = in_memory_container()
    app = create_app(container=container, identity_provider=DevIdentityProvider())
    with TestClient(app) as client:
        yield client, store


def _as(email: str) -> dict[str, str]:
    return {"X-Dev-User": email}


def _code(response: Any) -> str:
    code: str = response.json()["code"]
    return code


def test_health_stays_public(world: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = world
    assert client.get("/health").status_code == 200


def test_requests_need_an_identity(world: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = world
    response = client.get("/languages")
    assert (response.status_code, _code(response)) == (401, "unauthenticated")


def test_unknown_and_inactive_users_are_not_provisioned(
    world: tuple[TestClient, InMemoryStore],
) -> None:
    client, store = world
    response = client.get("/languages", headers=_as("stranger@example.org"))
    assert (response.status_code, _code(response)) == (403, "not_provisioned")

    user = seed_user(store, "gone@example.org", *Permission)
    user.set_active(False)
    response = client.get("/languages", headers=_as("gone@example.org"))
    assert (response.status_code, _code(response)) == (403, "not_provisioned")


def test_reads_need_only_authentication(world: tuple[TestClient, InMemoryStore]) -> None:
    client, store = world
    seed_user(store, "reader@example.org")
    for path in ("/languages", "/projects", "/intents", "/categories", "/permissions", "/me"):
        assert client.get(path, headers=_as("reader@example.org")).status_code == 200, path


def test_access_admin_endpoints_need_manage_access(
    world: tuple[TestClient, InMemoryStore],
) -> None:
    client, store = world
    seed_user(store, "author@example.org", Permission.AUTHOR_QASETS)
    seed_user(store, "admin@example.org", Permission.MANAGE_ACCESS)
    for path in ("/users", "/roles"):
        denied = client.get(path, headers=_as("author@example.org"))
        assert (denied.status_code, _code(denied)) == (403, "permission_denied")
        assert client.get(path, headers=_as("admin@example.org")).status_code == 200


def _qaset_world(client: TestClient, store: InMemoryStore) -> dict[str, str]:
    """Builds a QA set through the API as a user holding every permission."""
    seed_user(store, "root@example.org", *Permission)
    root = _as("root@example.org")

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = client.post(path, json=body, headers=root)
        assert response.status_code == 201, response.text
        created: dict[str, Any] = response.json()
        return created

    fr = post("/languages", {"code": "fr", "name": "French"})["id"]
    project = post("/projects", {"name": "P", "base_language_id": fr})["id"]
    protocol = post(f"/projects/{project}/protocols", {"name": "Pr"})["id"]
    theme = post(f"/protocols/{protocol}/themes", {"name": "T"})["id"]
    qaset = post(f"/themes/{theme}/qasets", {"language_id": fr, "answer_text": "a"})
    variant = post(f"/qasets/{qaset['id']}/languages/{fr}/variants", {"text": "q"})["id"]
    return {
        "fr": fr,
        "project": project,
        "theme": theme,
        "qaset": qaset["id"],
        "answer": qaset["languages"][0]["answer"]["id"],
        "variant": variant,
    }


WRITES = [
    (Permission.MANAGE_LANGUAGES, "post", "/languages", {"json": {"code": "en", "name": "E"}}),
    (
        Permission.MANAGE_CATALOG,
        "post",
        "/projects",
        {"json": {"name": "X", "base_language_id": "{fr}"}},
    ),
    (Permission.MANAGE_CATALOG, "patch", "/themes/{theme}", {"json": {"name": "T2"}}),
    (
        Permission.AUTHOR_QASETS,
        "post",
        "/themes/{theme}/qasets",
        {"json": {"language_id": "{fr}", "answer_text": "b"}},
    ),
    (
        Permission.AUTHOR_QASETS,
        "patch",
        "/qasets/{qaset}/variants/{variant}",
        {"json": {"text": "q2"}},
    ),
    (Permission.MANAGE_INTENTS, "post", "/intents", {"json": {"text": "Dosage"}}),
    (Permission.MANAGE_CATEGORIES, "post", "/categories", {"json": {"name": "Malaria"}}),
    (
        Permission.MANAGE_AUDIO,
        "post",
        "/qasets/{qaset}/answers/{answer}/audio",
        {"files": {"file": ("a.webm", b"sound", "audio/webm")}},
    ),
    (Permission.MANAGE_ACCESS, "post", "/roles", {"json": {"name": "Author", "permissions": []}}),
]


@pytest.mark.parametrize(("permission", "method", "path", "kwargs"), WRITES)
def test_writes_need_their_permission(
    world: tuple[TestClient, InMemoryStore],
    permission: Permission,
    method: str,
    path: str,
    kwargs: dict[str, Any],
) -> None:
    client, store = world
    ids = _qaset_world(client, store)
    others = [p for p in Permission if p is not permission]
    seed_user(store, "without@example.org", *others)
    seed_user(store, "with@example.org", permission)

    def call(email: str) -> Any:
        body = {
            key: {k: (v.format(**ids) if isinstance(v, str) else v) for k, v in value.items()}
            for key, value in kwargs.items()
        }
        return getattr(client, method)(path.format(**ids), headers=_as(email), **body)

    denied = call("without@example.org")
    assert (denied.status_code, _code(denied)) == (403, "permission_denied")
    assert call("with@example.org").status_code in (200, 201), call("with@example.org").text


def _walk(dependant: Dependant) -> Iterator[Any]:
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _walk(dependency)


def test_every_route_is_guarded() -> None:
    """Safety net: every route but /health authenticates, and every write checks a permission."""
    container, _ = in_memory_container()
    app = create_app(container=container, identity_provider=DevIdentityProvider())
    unguarded, unauthorized = [], []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path == "/health":
            continue
        calls = list(_walk(route.dependant))
        if current_user not in calls:
            unguarded.append(route.path)
        is_access_admin = route.path.startswith(("/users", "/roles"))
        if ((route.methods or set()) - {"GET"} or is_access_admin) and not any(
            isinstance(c, PermissionGuard) for c in calls
        ):
            unauthorized.append(f"{route.methods} {route.path}")
    assert unguarded == []
    assert unauthorized == []


def test_missing_provider_means_unauthenticated() -> None:
    container, store = in_memory_container()
    store.users.rows[uuid4()] = User.create(email="a@example.org", display_name="A")
    with TestClient(create_app(container=container)) as client:
        response = client.get("/languages", headers=_as("a@example.org"))
    assert (response.status_code, _code(response)) == (401, "unauthenticated")
