from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.domain.model.permission import Permission
from tests.fakes import ADMIN_EMAIL, admin_client, in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from tests.fakes import InMemoryStore


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryStore]]:
    container, store = in_memory_container()
    with admin_client(container, store) as client:
        yield client, store


def _ok(response: Any, status: int = 201) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


def _error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code


class World:
    """A project in French (fr, the base language) with a QA set in French and Bambara."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        self.bm = _ok(client.post("/languages", json={"code": "bm", "name": "Bambara"}))["id"]
        project = _ok(client.post("/projects", json={"name": "P", "base_language_id": self.fr}))
        protocol = _ok(client.post(f"/projects/{project['id']}/protocols", json={"name": "Pr"}))
        self.theme = _ok(client.post(f"/protocols/{protocol['id']}/themes", json={"name": "T"}))[
            "id"
        ]
        self.qaset = self.new_qaset(self.fr)
        bm = _ok(
            client.post(
                f"/qasets/{self.qaset}/languages",
                json={"language_id": self.bm, "answer_text": "b"},
            )
        )
        self.bm_answer = bm["answer"]["id"]
        self.fr_answer = self.presence(self.fr)["answer"]["id"]
        self.fr_variant = self.variant(self.fr)
        self.bm_variant = self.variant(self.bm)

    def new_qaset(self, language: str) -> str:
        body = {"language_id": language, "answer_text": "a"}
        return str(_ok(self.client.post(f"/themes/{self.theme}/qasets", json=body))["id"])

    def variant(self, language: str) -> str:
        url = f"/qasets/{self.qaset}/languages/{language}/variants"
        return str(_ok(self.client.post(url, json={"text": "q"}))["id"])

    def read(self) -> dict[str, Any]:
        return _ok(self.client.get(f"/qasets/{self.qaset}"), 200)

    def presence(self, language: str) -> dict[str, Any]:
        [presence] = [p for p in self.read()["languages"] if p["language_id"] == language]
        found: dict[str, Any] = presence
        return found


@pytest.fixture
def world(setup: tuple[TestClient, InMemoryStore]) -> World:
    return World(setup[0])


def test_clinical_validation_lifecycle(world: World) -> None:
    url = f"/qasets/{world.qaset}/clinical-validation"
    pending = _ok(world.client.get(url), 200)
    assert pending == {"kind": "clinical", "state": "pending", "history": []}
    assert world.read()["clinical_validation"] is None

    first = _ok(world.client.post(url, json={"decision": "validated", "note": "Checked"}))
    again = _ok(world.client.post(url, json={"decision": "rejected"}), 200)

    assert first["state"] == "validated"
    assert again["state"] == "rejected"
    assert again["history"] == [
        {
            "from_state": None,
            "to_state": "validated",
            "note": "Checked",
            "actor_email": ADMIN_EMAIL,
            "occurred_at": "2026-10-24T12:00:00Z",
        },
        {
            "from_state": "validated",
            "to_state": "rejected",
            "note": None,
            "actor_email": ADMIN_EMAIL,
            "occurred_at": "2026-10-24T12:00:00Z",
        },
    ]
    assert _ok(world.client.get(url), 200) == again
    assert world.read()["clinical_validation"] == {"state": "rejected"}


def test_clinical_needs_a_base_language_answer(world: World) -> None:
    bambara_only = world.new_qaset(world.bm)
    _error(
        world.client.post(
            f"/qasets/{bambara_only}/clinical-validation", json={"decision": "validated"}
        ),
        409,
        "no_base_language_presence",
    )


def test_translation_validation_of_answers_and_variants(world: World) -> None:
    answer_url = f"/answers/{world.bm_answer}/translation-validation"
    variant_url = f"/variants/{world.bm_variant}/translation-validation"

    answer = _ok(world.client.post(answer_url, json={"decision": "validated"}))
    variant = _ok(world.client.post(variant_url, json={"decision": "rejected", "note": "No"}))

    assert (answer["kind"], answer["state"]) == ("translation", "validated")
    assert variant["history"][0]["note"] == "No"
    assert _ok(world.client.get(variant_url), 200) == variant
    bm = world.presence(world.bm)
    assert bm["answer"]["translation_validation"] == {"state": "validated"}
    assert bm["variants"][0]["translation_validation"] == {"state": "rejected"}
    fr = world.presence(world.fr)
    assert fr["answer"]["translation_validation"] is None
    assert fr["variants"][0]["translation_validation"] is None


def test_base_language_items_are_not_translations(world: World) -> None:
    for url in (
        f"/answers/{world.fr_answer}/translation-validation",
        f"/variants/{world.fr_variant}/translation-validation",
    ):
        _error(world.client.post(url, json={"decision": "validated"}), 422, "not_a_translation")


def test_audio_validation(world: World) -> None:
    url = f"/qasets/{world.qaset}/variants/{world.bm_variant}/audio"
    audio = _ok(world.client.post(url, files={"file": ("a.webm", b"sound", "audio/webm")}))
    validation_url = f"/audios/{audio['audio_id']}/audio-validation"

    body = _ok(world.client.post(validation_url, json={"decision": "validated"}))

    assert (body["kind"], body["state"]) == ("audio", "validated")
    assert _ok(world.client.get(validation_url), 200) == body
    variant = world.presence(world.bm)["variants"][0]
    assert variant["audio"]["audio_validation"] == {"state": "validated"}


def test_errors(world: World) -> None:
    client = world.client
    decision = {"decision": "validated"}
    _error(
        client.post(f"/qasets/{uuid4()}/clinical-validation", json=decision), 404, "qaset_not_found"
    )
    _error(client.get(f"/qasets/{uuid4()}/clinical-validation"), 404, "qaset_not_found")
    _error(
        client.post(f"/answers/{uuid4()}/translation-validation", json=decision),
        404,
        "answer_not_found",
    )
    _error(client.get(f"/variants/{uuid4()}/translation-validation"), 404, "variant_not_found")
    _error(
        client.post(f"/audios/{uuid4()}/audio-validation", json=decision), 404, "audio_not_found"
    )
    url = f"/qasets/{world.qaset}/clinical-validation"
    _error(client.post(url, json={"decision": "pending"}), 422, "invalid_decision")
    _error(client.post(url, json={"decision": "validated", "actor": "x"}), 422, "invalid_request")
    _error(client.post(url, json={}), 422, "invalid_request")


def test_history_never_shows_the_identity_subject(world: World) -> None:
    url = f"/qasets/{world.qaset}/clinical-validation"
    body = _ok(world.client.post(url, json={"decision": "validated"}))
    for event in body["history"]:
        assert set(event) == {"from_state", "to_state", "note", "actor_email", "occurred_at"}


ENDPOINTS = [
    (Permission.VALIDATE_CLINICAL, "/qasets/{qaset}/clinical-validation"),
    (Permission.VALIDATE_TRANSLATION, "/answers/{bm_answer}/translation-validation"),
    (Permission.VALIDATE_TRANSLATION, "/variants/{bm_variant}/translation-validation"),
]


@pytest.mark.parametrize(("permission", "path"), ENDPOINTS)
def test_each_endpoint_needs_its_own_permission(
    setup: tuple[TestClient, InMemoryStore], world: World, permission: Permission, path: str
) -> None:
    client, store = setup
    url = path.format(qaset=world.qaset, bm_answer=world.bm_answer, bm_variant=world.bm_variant)
    seed_user(store, "without@example.org", *[p for p in Permission if p is not permission])
    seed_user(store, "with@example.org", permission)
    without, with_ = {"X-Dev-User": "without@example.org"}, {"X-Dev-User": "with@example.org"}

    for method, kwargs in (("get", {}), ("post", {"json": {"decision": "validated"}})):
        denied = getattr(client, method)(url, headers=without, **kwargs)
        assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
        assert getattr(client, method)(url, headers=with_, **kwargs).status_code in (200, 201)


def test_audio_validation_needs_validate_audio(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    client, store = setup
    upload = f"/qasets/{world.qaset}/answers/{world.fr_answer}/audio"
    audio = _ok(client.post(upload, files={"file": ("a.webm", b"sound", "audio/webm")}))
    url = f"/audios/{audio['audio_id']}/audio-validation"
    seed_user(store, "recorder@example.org", Permission.MANAGE_AUDIO, Permission.VALIDATE_CLINICAL)
    seed_user(store, "reviewer@example.org", Permission.VALIDATE_AUDIO)

    denied = client.post(
        url, json={"decision": "validated"}, headers={"X-Dev-User": "recorder@example.org"}
    )
    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
    assert client.get(url, headers={"X-Dev-User": "recorder@example.org"}).status_code == 403
    allowed = client.post(
        url, json={"decision": "validated"}, headers={"X-Dev-User": "reviewer@example.org"}
    )
    assert allowed.status_code == 201


def test_editing_validated_content_resets_it_to_pending(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    client, store = setup
    seed_user(store, "editor@example.org", Permission.AUTHOR_QASETS)
    editor = {"X-Dev-User": "editor@example.org"}
    clinical_url = f"/qasets/{world.qaset}/clinical-validation"
    translation_url = f"/answers/{world.bm_answer}/translation-validation"
    _ok(client.post(clinical_url, json={"decision": "validated"}))
    _ok(client.post(translation_url, json={"decision": "validated"}))

    edited = client.patch(
        f"/qasets/{world.qaset}/languages/{world.fr}", json={"text": "new"}, headers=editor
    )
    assert edited.status_code == 200, edited.text

    read = world.read()
    assert read["clinical_validation"] is None
    bm = next(p for p in read["languages"] if p["language_id"] == world.bm)
    assert bm["answer"]["translation_validation"] == {"state": "validated"}
    history = _ok(client.get(clinical_url), 200)
    assert history["state"] == "pending"
    assert history["history"][-1] == {
        "from_state": "validated",
        "to_state": "pending",
        "note": "content changed",
        "actor_email": "editor@example.org",
        "occurred_at": "2026-10-24T12:00:00Z",
    }

    client.patch(f"/qasets/{world.qaset}/languages/{world.bm}", json={"text": "nb"}, headers=editor)
    assert _ok(client.get(translation_url), 200)["state"] == "pending"
    assert (
        _ok(client.post(clinical_url, json={"decision": "validated"}), 200)["state"] == "validated"
    )
