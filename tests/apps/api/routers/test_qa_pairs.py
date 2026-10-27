from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.application.author_qa_pairs.command import MAX_QA_PAIRS
from qa_authoring.domain.model.permission import Permission
from tests.fakes import admin_client, in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from tests.fakes import InMemoryStore


def _ok(response: Any, status: int = 201) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryStore, dict[str, str]]]:
    container, store = in_memory_container()
    with admin_client(container, store) as client:
        fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        bm = _ok(client.post("/languages", json={"code": "bm", "name": "Bambara"}))["id"]
        project = _ok(client.post("/projects", json={"name": "P", "base_language_id": bm}))["id"]
        protocol = _ok(client.post(f"/projects/{project}/protocols", json={"name": "Pr"}))["id"]
        theme = _ok(client.post(f"/protocols/{protocol}/themes", json={"name": "T"}))["id"]
        yield client, store, {"fr": fr, "bm": bm, "project": project, "theme": theme}


def test_pairs_are_authored_in_the_base_language_and_summarized(
    setup: tuple[TestClient, InMemoryStore, dict[str, str]],
) -> None:
    client, _, ids = setup
    url = f"/themes/{ids['theme']}/qa-pairs"
    pairs = [
        {"question": "Q1", "answer": "A"},
        {"question": "Q2", "answer": "A"},
        {"question": "Q1", "answer": "A"},
    ]

    summary = _ok(client.post(url, json=pairs), 200)
    again = _ok(client.post(url, json=[{"question": "Q3", "answer": " A "}]), 200)

    assert summary == {
        "qasets_created": 1,
        "qasets_updated": 0,
        "variants_added": 2,
        "skipped_rows": [2],
    }
    assert again == {
        "qasets_created": 0,
        "qasets_updated": 1,
        "variants_added": 1,
        "skipped_rows": [],
    }
    [qaset] = _ok(client.get(f"/themes/{ids['theme']}/qasets"), 200)["items"]
    full = _ok(client.get(f"/qasets/{qaset['id']}"), 200)
    [language] = full["languages"]
    assert language["language_id"] == ids["bm"]
    assert [v["text"] for v in language["variants"]] == ["Q1", "Q2", "Q3"]


def test_no_language_can_be_given(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, _, ids = setup
    body = [{"question": "Q", "answer": "A", "language_id": ids["fr"]}]
    response = client.post(f"/themes/{ids['theme']}/qa-pairs", json=body)
    assert (response.status_code, response.json()["code"]) == (422, "invalid_request")


def test_empty_fields_are_rejected_with_their_rows(
    setup: tuple[TestClient, InMemoryStore, dict[str, str]],
) -> None:
    client, store, ids = setup
    pairs = [
        {"question": "Q1", "answer": "A"},
        {"question": " ", "answer": "A"},
        {"question": "Q3", "answer": ""},
    ]
    response = client.post(f"/themes/{ids['theme']}/qa-pairs", json=pairs)
    assert response.status_code == 422, response.text
    body = response.json()
    assert (body["code"], body["details"]) == ("invalid_qa_pairs", {"rows": [1, 2]})
    assert store.qasets.rows == {}


def test_unknown_theme_and_scope(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, store, ids = setup
    pairs = [{"question": "Q", "answer": "A"}]
    missing = client.post(f"/themes/{uuid4()}/qa-pairs", json=pairs)
    assert (missing.status_code, missing.json()["code"]) == (404, "theme_not_found")

    seed_user(store, "elsewhere@example.org", Permission.AUTHOR_QASETS, project_id=uuid4())
    denied = client.post(
        f"/themes/{ids['theme']}/qa-pairs",
        json=pairs,
        headers={"X-Dev-User": "elsewhere@example.org"},
    )
    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")


def test_a_batch_is_capped(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, store, ids = setup
    url = f"/themes/{ids['theme']}/qa-pairs"
    assert MAX_QA_PAIRS == 500

    def batch(size: int) -> list[dict[str, str]]:
        return [{"question": f"Q{n}", "answer": f"A{n % 7}"} for n in range(size)]

    over = client.post(url, json=batch(MAX_QA_PAIRS + 1))
    assert (over.status_code, over.json()["code"]) == (422, "invalid_request")
    assert store.qasets.rows == {}
    at_limit = _ok(client.post(url, json=batch(MAX_QA_PAIRS)), 200)
    assert (at_limit["qasets_created"], at_limit["variants_added"]) == (7, MAX_QA_PAIRS)
