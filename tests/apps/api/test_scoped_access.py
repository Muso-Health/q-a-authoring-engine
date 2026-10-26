from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from qa_authoring.domain.model.permission import Permission
from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from tests.fakes import in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.fakes import InMemoryStore

ROOT = "root@example.org"


def _as(email: str) -> dict[str, str]:
    return {"X-Dev-User": email}


def _body(response: Any, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


class World:
    """Two projects (base fr), each with a protocol, a theme and a QA set answered in fr and bm,
    built through the API by a global admin."""

    def __init__(self, client: TestClient, store: InMemoryStore) -> None:
        self.client, self.store = client, store
        seed_user(store, ROOT, *Permission)
        self.fr = self._post("/languages", {"code": "fr", "name": "French"})["id"]
        self.bm = self._post("/languages", {"code": "bm", "name": "Bambara"})["id"]
        self.ids: dict[str, dict[str, str]] = {}
        for name in ("p1", "p2"):
            project = self._post("/projects", {"name": name.upper(), "base_language_id": self.fr})
            protocol = self._post(f"/projects/{project['id']}/protocols", {"name": "Pr"})
            theme = self._post(f"/protocols/{protocol['id']}/themes", {"name": "T"})
            qaset = self._post(
                f"/themes/{theme['id']}/qasets", {"language_id": self.fr, "answer_text": "a"}
            )
            bm = self._post(
                f"/qasets/{qaset['id']}/languages", {"language_id": self.bm, "answer_text": "b"}
            )
            self.ids[name] = {
                "project": project["id"],
                "protocol": protocol["id"],
                "theme": theme["id"],
                "qaset": qaset["id"],
                "fr_answer": qaset["languages"][0]["answer"]["id"],
                "bm_answer": bm["answer"]["id"],
            }

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return _body(self.client.post(path, json=body, headers=_as(ROOT)), 201)

    def project(self, name: str) -> str:
        return self.ids[name]["project"]


@pytest.fixture
def world() -> Iterator[World]:
    container, store = in_memory_container()
    app = create_app(container=container, identity_provider=DevIdentityProvider())
    with TestClient(app) as client:
        yield World(client, store)


def _status(world: World, email: str, method: str, path: str, **kwargs: Any) -> int:
    response = getattr(world.client, method)(path, headers=_as(email), **kwargs)
    if response.status_code == 403:
        assert response.json()["code"] == "permission_denied"
    status: int = response.status_code
    return status


# ── guards per permission class ──────────────────────────────────────────────────────────────────


def test_a_project_scoped_author_writes_inside_its_project_only(world: World) -> None:
    seed_user(
        world.store, "author@example.org", Permission.AUTHOR_QASETS, project_id=world.project("p1")
    )
    for name, expected in (("p1", 201), ("p2", 403)):
        theme = world.ids[name]["theme"]
        body = {"language_id": world.fr, "answer_text": "new"}
        status = _status(world, "author@example.org", "post", f"/themes/{theme}/qasets", json=body)
        assert status == expected, name
        qaset = world.ids[name]["qaset"]
        patch = _status(
            world,
            "author@example.org",
            "patch",
            f"/qasets/{qaset}/languages/{world.bm}",
            json={"text": "edited"},
        )
        assert patch == (200 if name == "p1" else 403), name


def test_a_project_only_author_covers_every_language(world: World) -> None:
    seed_user(
        world.store,
        "author@example.org",
        Permission.AUTHOR_QASETS,
        project_id=world.project("p1"),
        language_id=world.fr,
    )
    qaset = world.ids["p1"]["qaset"]
    status = _status(
        world,
        "author@example.org",
        "patch",
        f"/qasets/{qaset}/languages/{world.bm}",
        json={"text": "edited"},
    )
    assert status == 200


def test_clinical_validation_is_checked_against_the_qaset_project(world: World) -> None:
    seed_user(
        world.store,
        "clinician@example.org",
        Permission.VALIDATE_CLINICAL,
        project_id=world.project("p2"),
    )
    decision = {"decision": "validated"}
    for name, expected in (("p1", 403), ("p2", 201)):
        qaset = world.ids[name]["qaset"]
        path = f"/qasets/{qaset}/clinical-validation"
        assert _status(world, "clinician@example.org", "post", path, json=decision) == expected


def test_translation_validation_respects_the_item_language(world: World) -> None:
    seed_user(
        world.store,
        "bm@example.org",
        Permission.VALIDATE_TRANSLATION,
        project_id=world.project("p1"),
        language_id=world.bm,
    )
    seed_user(world.store, "fr@example.org", Permission.VALIDATE_TRANSLATION, language_id=world.fr)
    decision = {"decision": "validated"}
    p1, p2 = world.ids["p1"]["bm_answer"], world.ids["p2"]["bm_answer"]
    path = "/answers/{}/translation-validation"
    assert _status(world, "bm@example.org", "post", path.format(p1), json=decision) == 201
    assert _status(world, "bm@example.org", "post", path.format(p2), json=decision) == 403
    assert _status(world, "fr@example.org", "post", path.format(p1), json=decision) == 403
    assert _status(world, "bm@example.org", "get", path.format(p1)) == 200
    assert _status(world, "bm@example.org", "get", path.format(p2)) == 403


def test_audio_permissions_follow_the_bound_item_language(world: World) -> None:
    seed_user(
        world.store,
        "recorder@example.org",
        Permission.MANAGE_AUDIO,
        Permission.VALIDATE_AUDIO,
        project_id=world.project("p1"),
        language_id=world.bm,
    )
    qaset, fr_answer, bm_answer = (world.ids["p1"][k] for k in ("qaset", "fr_answer", "bm_answer"))
    files = {"file": ("a.webm", b"sound", "audio/webm")}
    path = "/qasets/{}/answers/{}/audio"
    denied = _status(
        world, "recorder@example.org", "post", path.format(qaset, fr_answer), files=files
    )
    assert denied == 403
    created = world.client.post(
        path.format(qaset, bm_answer), files=files, headers=_as("recorder@example.org")
    )
    audio_id = _body(created, 201)["audio_id"]
    validation = f"/audios/{audio_id}/audio-validation"
    decision = {"decision": "validated"}
    assert _status(world, "recorder@example.org", "post", validation, json=decision) == 201
    seed_user(
        world.store,
        "fr-reviewer@example.org",
        Permission.VALIDATE_AUDIO,
        project_id=world.project("p1"),
        language_id=world.fr,
    )
    assert _status(world, "fr-reviewer@example.org", "post", validation, json=decision) == 403


def test_export_is_checked_against_the_project(world: World) -> None:
    seed_user(
        world.store,
        "exporter@example.org",
        Permission.EXPORT_CORPUS,
        project_id=world.project("p1"),
    )
    p2 = world.project("p2")
    assert _status(world, "exporter@example.org", "post", f"/projects/{p2}/export") == 403
    # Inside its scope the guard lets it through; nothing is validated yet.
    p1 = world.project("p1")
    assert _status(world, "exporter@example.org", "post", f"/projects/{p1}/export") == 409


def test_global_permissions_ignore_the_assignment_scope(world: World) -> None:
    seed_user(
        world.store,
        "curator@example.org",
        Permission.MANAGE_CATALOG,
        project_id=world.project("p1"),
    )
    theme = world.ids["p2"]["theme"]
    status = _status(world, "curator@example.org", "patch", f"/themes/{theme}", json={"name": "T2"})
    assert status == 200


def test_a_missing_resource_is_not_found_rather_than_denied(world: World) -> None:
    seed_user(
        world.store, "author@example.org", Permission.AUTHOR_QASETS, project_id=world.project("p1")
    )
    body = {"language_id": world.fr, "answer_text": "x"}
    response = world.client.post(
        f"/themes/{uuid4()}/qasets", json=body, headers=_as("author@example.org")
    )
    assert (response.status_code, response.json()["code"]) == (404, "theme_not_found")


# ── visibility ───────────────────────────────────────────────────────────────────────────────────


def test_projects_are_listed_only_when_visible(world: World) -> None:
    seed_user(world.store, "scoped@example.org", project_id=world.project("p1"))
    seed_user(world.store, "global@example.org", Permission.MANAGE_LANGUAGES)
    seed_user(world.store, "nobody@example.org")

    def names(email: str) -> list[str]:
        items = _body(world.client.get("/projects", headers=_as(email)), 200)["items"]
        return [item["name"] for item in items]

    assert names("scoped@example.org") == ["P1"]
    assert names("global@example.org") == ["P1", "P2"]
    assert names("nobody@example.org") == []


def test_a_hidden_project_is_not_found_at_every_level(world: World) -> None:
    seed_user(world.store, "scoped@example.org", project_id=world.project("p1"))
    hidden, shown = world.ids["p2"], world.ids["p1"]
    paths = [
        ("/projects/{project}", "project_not_found"),
        ("/projects/{project}/protocols", "project_not_found"),
        ("/protocols/{protocol}", "protocol_not_found"),
        ("/protocols/{protocol}/themes", "protocol_not_found"),
        ("/themes/{theme}", "theme_not_found"),
        ("/themes/{theme}/qasets", "theme_not_found"),
        ("/themes/{theme}/documentation", "theme_not_found"),
        ("/qasets/{qaset}", "qaset_not_found"),
    ]
    for path, code in paths:
        response = world.client.get(path.format(**hidden), headers=_as("scoped@example.org"))
        assert (response.status_code, response.json()["code"]) == (404, code), path
        visible = world.client.get(path.format(**shown), headers=_as("scoped@example.org"))
        assert visible.status_code == 200, path


# ── admin assignment API and the views of a user ─────────────────────────────────────────────────


def test_assign_and_unassign_scoped_roles(world: World) -> None:
    root = _as(ROOT)
    role = _body(
        world.client.post(
            "/roles",
            json={"name": "Reviewer", "permissions": ["validate_translation"]},
            headers=root,
        ),
        201,
    )
    user = _body(
        world.client.post(
            "/users", json={"email": "ada@example.org", "display_name": "Ada"}, headers=root
        ),
        201,
    )
    assert (user["assignments"], user["grants"]) == ([], [])
    url = f"/users/{user['id']}/assignments"
    p1 = world.project("p1")
    body = {"role_id": role["id"], "project_id": p1, "language_id": world.bm}
    assigned = _body(world.client.post(url, json=body, headers=root), 201)
    [assignment] = assigned["assignments"]
    assert assignment == {
        "id": assignment["id"],
        "role": {"id": role["id"], "name": "Reviewer"},
        "project": {"id": p1, "name": "P1"},
        "language": {"id": world.bm, "code": "bm", "name": "Bambara"},
    }
    assert assigned["grants"] == [
        {"permission": "validate_translation", "project_id": p1, "language_id": world.bm}
    ]
    assert _body(world.client.post(url, json=body, headers=root), 200) == assigned

    everywhere = _body(world.client.post(url, json={"role_id": role["id"]}, headers=root), 201)
    wildcard = next(a for a in everywhere["assignments"] if a["project"] is None)
    assert wildcard["language"] is None
    assert _body(world.client.get(f"/users/{user['id']}", headers=root), 200) == everywhere

    deleted = world.client.delete(f"{url}/{assignment['id']}", headers=root)
    assert deleted.status_code == 204
    remaining = _body(world.client.get(f"/users/{user['id']}", headers=root), 200)
    assert [a["id"] for a in remaining["assignments"]] == [wildcard["id"]]
    again = world.client.delete(f"{url}/{assignment['id']}", headers=root)
    assert (again.status_code, again.json()["code"]) == (404, "assignment_not_found")


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("role_id", "role_not_found"),
        ("project_id", "project_not_found"),
        ("language_id", "language_not_found"),
    ],
)
def test_assignment_references_must_exist(world: World, field: str, code: str) -> None:
    root = _as(ROOT)
    role = _body(
        world.client.post("/roles", json={"name": "R", "permissions": []}, headers=root), 201
    )
    user = _body(
        world.client.post(
            "/users", json={"email": "a@example.org", "display_name": "A"}, headers=root
        ),
        201,
    )
    body = {"role_id": role["id"], "project_id": world.project("p1"), "language_id": world.bm}
    body[field] = str(uuid4())
    response = world.client.post(f"/users/{user['id']}/assignments", json=body, headers=root)
    assert (response.status_code, response.json()["code"]) == (404, code)


def test_me_exposes_scoped_assignments_and_grants_without_the_subject(world: World) -> None:
    p1 = world.project("p1")
    seed_user(
        world.store,
        "me@example.org",
        Permission.VALIDATE_AUDIO,
        project_id=p1,
        language_id=world.bm,
    )
    me = _body(world.client.get("/me", headers=_as("me@example.org")), 200)
    assert set(me) == {"id", "email", "display_name", "permissions", "assignments", "grants"}
    assert me["permissions"] == ["validate_audio"]
    [assignment] = me["assignments"]
    assert (assignment["project"], assignment["language"]) == (
        {"id": p1, "name": "P1"},
        {"id": world.bm, "code": "bm", "name": "Bambara"},
    )
    assert me["grants"] == [
        {"permission": "validate_audio", "project_id": p1, "language_id": world.bm}
    ]
    assert "subject" not in str(me) and "oid" not in me
