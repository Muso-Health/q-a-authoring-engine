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


@pytest.fixture
def url(setup: tuple[TestClient, InMemoryStore]) -> str:
    client, _ = setup
    fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
    project = _ok(client.post("/projects", json={"name": "P", "base_language_id": fr}))["id"]
    protocol = _ok(client.post(f"/projects/{project}/protocols", json={"name": "Pr"}))["id"]
    theme = _ok(client.post(f"/protocols/{protocol}/themes", json={"name": "T"}))["id"]
    qaset = _ok(
        client.post(f"/themes/{theme}/qasets", json={"language_id": fr, "answer_text": "Buvez."})
    )
    answer = qaset["languages"][0]["answer"]["id"]
    return f"/qasets/{qaset['id']}/answers/{answer}/generate-variants"


def test_returns_candidates_without_saving_them(
    setup: tuple[TestClient, InMemoryStore], url: str
) -> None:
    client, store = setup
    store.llm.reply = '["Que faire ?", " Que faire ? ", "Et après ?"]'

    body = _ok(client.post(url, json={"context": "Fièvre"}), 200)

    assert body == {"candidates": ["Que faire ?", "Et après ?"]}
    prompt = store.llm.prompts[0]
    assert "Fièvre" in prompt and "Buvez." in prompt and "French" in prompt
    qaset = next(iter(store.qasets.rows.values()))
    assert qaset.variants == ()


def test_context_is_optional(setup: tuple[TestClient, InMemoryStore], url: str) -> None:
    client, store = setup
    store.llm.reply = '["Que faire ?"]'
    assert _ok(client.post(url, json={}), 200) == {"candidates": ["Que faire ?"]}


def test_errors(setup: tuple[TestClient, InMemoryStore], url: str) -> None:
    client, store = setup
    store.llm.reply = "not a list"
    failed = client.post(url, json={"context": ""})
    assert (failed.status_code, failed.json()["code"]) == (502, "generation_engine_error")
    store.llm.failing = True
    assert client.post(url, json={}).json()["code"] == "generation_engine_error"

    qaset_id = url.split("/")[2]
    missing_answer = client.post(f"/qasets/{qaset_id}/answers/{uuid4()}/generate-variants", json={})
    assert (missing_answer.status_code, missing_answer.json()["code"]) == (404, "answer_not_found")
    missing_qaset = client.post(f"/qasets/{uuid4()}/answers/{uuid4()}/generate-variants", json={})
    assert (missing_qaset.status_code, missing_qaset.json()["code"]) == (404, "qaset_not_found")
    assert client.post(url, json={"context": "x", "extra": 1}).status_code == 422


def test_generation_needs_author_qasets(setup: tuple[TestClient, InMemoryStore], url: str) -> None:
    client, store = setup
    seed_user(
        store, "reviewer@example.org", *[p for p in Permission if p is not Permission.AUTHOR_QASETS]
    )
    denied = client.post(url, json={}, headers={"X-Dev-User": "reviewer@example.org"})
    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
