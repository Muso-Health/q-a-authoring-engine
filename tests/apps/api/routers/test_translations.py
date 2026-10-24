from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    PromptTemplate,
    PromptTemplateKey,
)
from tests.fakes import NOW, admin_client, in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from tests.fakes import InMemoryStore


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryStore]]:
    container, store = in_memory_container()
    for key in PromptTemplateKey:
        store.prompt_templates.rows[key] = PromptTemplate.create(
            key, DEFAULT_TEMPLATES[key], updated_by=None, at=NOW
        )
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
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        self.bm = _ok(client.post("/languages", json={"code": "bm", "name": "Bambara"}))["id"]
        project = _ok(client.post("/projects", json={"name": "P", "base_language_id": self.fr}))
        protocol = _ok(client.post(f"/projects/{project['id']}/protocols", json={"name": "Pr"}))
        theme = _ok(client.post(f"/protocols/{protocol['id']}/themes", json={"name": "T"}))
        qaset = _ok(
            client.post(
                f"/themes/{theme['id']}/qasets",
                json={"language_id": self.fr, "answer_text": "Buvez de l'eau."},
            )
        )
        self.qaset = qaset["id"]
        self.answer = qaset["languages"][0]["answer"]["id"]
        self.variant = _ok(
            client.post(
                f"/qasets/{self.qaset}/languages/{self.fr}/variants", json={"text": "Que faire ?"}
            )
        )["id"]

    def translate_answer(self, target: str, engine: str = "google", **headers: str) -> Any:
        return self.client.post(
            f"/qasets/{self.qaset}/answers/{self.answer}/translate",
            json={"target_language_id": target, "engine": engine},
            headers=headers or None,
        )

    def translate_variant(self, target: str, engine: str = "google") -> Any:
        return self.client.post(
            f"/qasets/{self.qaset}/variants/{self.variant}/translate",
            json={"target_language_id": target, "engine": engine},
        )

    def read(self) -> dict[str, Any]:
        return _ok(self.client.get(f"/qasets/{self.qaset}"), 200)


@pytest.fixture
def world(setup: tuple[TestClient, InMemoryStore]) -> World:
    return World(setup[0])


def test_translate_answer_with_google(world: World) -> None:
    body = _ok(world.translate_answer(world.bm))

    presence = body["presence"]
    assert presence["language_id"] == world.bm
    assert presence["answer"]["text"] == "bm: Buvez de l'eau."
    assert presence["answer"]["translation_validation"] is None
    new_answer = presence["answer"]["id"]
    assert set(body["link"]["answer_ids"]) == {world.answer, new_answer}

    languages = {p["language_id"]: p for p in world.read()["languages"]}
    assert languages[world.fr]["answer"]["links"] == [
        {"link_id": body["link"]["id"], "other_id": new_answer, "other_language_id": world.bm}
    ]
    assert languages[world.bm]["answer"]["links"] == [
        {"link_id": body["link"]["id"], "other_id": world.answer, "other_language_id": world.fr}
    ]


def test_translate_with_the_llm_engine(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    _, store = setup
    body = _ok(world.translate_answer(world.bm, engine="llm"))
    assert body["presence"]["answer"]["text"] == "Traduction du modèle"
    assert "from French into Bambara" in store.llm.prompts[0]


def test_translate_variant(world: World) -> None:
    _error(world.translate_variant(world.bm), 409, "language_presence_required")
    _ok(world.translate_answer(world.bm))

    body = _ok(world.translate_variant(world.bm))

    variant = body["variant"]
    assert (variant["language_id"], variant["text"]) == (world.bm, "bm: Que faire ?")
    assert set(body["link"]["variant_ids"]) == {world.variant, variant["id"]}
    bm = next(p for p in world.read()["languages"] if p["language_id"] == world.bm)
    assert bm["variants"][0]["links"][0]["other_id"] == world.variant


def test_errors(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, store = setup
    _error(world.translate_answer(world.fr), 422, "same_language")
    _error(world.translate_answer(str(uuid4())), 422, "unknown_language")
    _error(world.translate_answer(world.bm, engine="babelfish"), 422, "unknown_engine")
    _error(
        client.post(
            f"/qasets/{uuid4()}/answers/{world.answer}/translate",
            json={"target_language_id": world.bm, "engine": "google"},
        ),
        404,
        "qaset_not_found",
    )
    _error(
        client.post(
            f"/qasets/{world.qaset}/answers/{uuid4()}/translate",
            json={"target_language_id": world.bm, "engine": "google"},
        ),
        404,
        "answer_not_found",
    )
    _error(
        client.post(
            f"/qasets/{world.qaset}/variants/{uuid4()}/translate",
            json={"target_language_id": world.bm, "engine": "google"},
        ),
        404,
        "variant_not_found",
    )
    _error(
        client.post(f"/qasets/{world.qaset}/answers/{world.answer}/translate", json={}),
        422,
        "invalid_request",
    )

    store.google_translator.unsupported = {"bm"}
    _error(world.translate_answer(world.bm), 422, "unsupported_language_for_engine")
    store.google_translator.unsupported = set()

    store.google_translator.failing = True
    _error(world.translate_answer(world.bm), 502, "translation_engine_error")
    assert [p["language_id"] for p in world.read()["languages"]] == [world.fr]
    store.google_translator.failing = False

    _ok(world.translate_answer(world.bm))
    _error(world.translate_answer(world.bm), 409, "language_already_present")


def test_translation_needs_author_qasets(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    _, store = setup
    seed_user(
        store, "reviewer@example.org", *[p for p in Permission if p is not Permission.AUTHOR_QASETS]
    )
    denied = world.translate_answer(world.bm, **{"X-Dev-User": "reviewer@example.org"})
    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
