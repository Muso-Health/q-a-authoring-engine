from __future__ import annotations

import hashlib
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
    assert response.json()["code"] == code


def _file(content: bytes, filename: str = "guide.txt", mime: str = "text/plain") -> Any:
    return {"file": (filename, content, mime)}


class World:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        project = _ok(client.post("/projects", json={"name": "P", "base_language_id": self.fr}))
        protocol = _ok(client.post(f"/projects/{project['id']}/protocols", json={"name": "Pr"}))
        self.theme = _ok(client.post(f"/protocols/{protocol['id']}/themes", json={"name": "T"}))[
            "id"
        ]
        self.url = f"/themes/{self.theme}/documentation"

    def qaset(self, answer: str) -> None:
        body = {"language_id": self.fr, "answer_text": answer}
        _ok(self.client.post(f"/themes/{self.theme}/qasets", json=body))


@pytest.fixture
def world(setup: tuple[TestClient, InMemoryStore]) -> World:
    return World(setup[0])


def test_upload_list_download_and_delete(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    client, store = setup
    content = b"Malaria causes fever."

    body = _ok(client.post(world.url, files=_file(content)))

    assert body == {
        "id": body["id"],
        "theme_id": world.theme,
        "filename": "guide.txt",
        "mime_type": "text/plain",
        "size_bytes": len(content),
        "checksum_sha256": hashlib.sha256(content).hexdigest(),
        "created_at": "2026-10-24T12:00:00Z",
    }
    assert _ok(client.get(world.url), 200) == {"items": [body]}
    download = _ok(client.get(f"/documentation/{body['id']}/download-url"), 200)
    assert download["url"].endswith("?ttl=600")
    assert download["expires_at"] == "2026-10-24T12:10:00Z"

    assert client.delete(f"{world.url}/{body['id']}").status_code == 204
    assert _ok(client.get(world.url), 200) == {"items": []}
    assert store.documentation_storage.blobs == {}


def test_upload_errors(world: World) -> None:
    client = world.client
    _error(
        client.post(world.url, files=_file(b"<html>", "a.html", "text/html")),
        422,
        "unsupported_document_type",
    )
    _error(client.post(world.url, files=_file(b"x" * 257)), 422, "document_too_large")
    _error(
        client.post(f"/themes/{uuid4()}/documentation", files=_file(b"x")), 404, "theme_not_found"
    )
    _error(client.get(f"/themes/{uuid4()}/documentation"), 404, "theme_not_found")
    _error(client.delete(f"{world.url}/{uuid4()}"), 404, "documentation_not_found")
    _error(client.get(f"/documentation/{uuid4()}/download-url"), 404, "documentation_not_found")
    _error(client.post(world.url), 422, "invalid_request")


def test_completeness(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, store = setup
    completeness = f"/themes/{world.theme}/completeness"
    _error(client.post(completeness), 409, "no_documentation")

    _ok(client.post(world.url, files=_file(b"Malaria: prevention, dosage, danger signs.")))
    world.qaset("Use a bed net.")
    store.llm.reply = '["Dosage", "Danger signs"]'

    body = _ok(client.post(completeness), 200)

    assert body == {"uncovered_notions": ["Dosage", "Danger signs"]}
    prompt = store.llm.prompts[-1]
    assert "Malaria: prevention, dosage, danger signs." in prompt
    assert "Use a bed net." in prompt and "French" in prompt

    store.llm.reply = "not a list"
    _error(client.post(completeness), 502, "completeness_engine_error")
    _error(client.post(f"/themes/{uuid4()}/completeness"), 404, "theme_not_found")


def test_permissions(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, store = setup
    doc = _ok(client.post(world.url, files=_file(b"Malaria.")))
    seed_user(store, "reader@example.org")
    seed_user(store, "author@example.org", Permission.AUTHOR_QASETS)
    reader, author = {"X-Dev-User": "reader@example.org"}, {"X-Dev-User": "author@example.org"}

    assert client.get(world.url, headers=reader).status_code == 200
    assert client.get(f"/documentation/{doc['id']}/download-url", headers=reader).status_code == 200
    for response in (
        client.post(world.url, files=_file(b"x"), headers=author),
        client.delete(f"{world.url}/{doc['id']}", headers=author),
        client.post(f"/themes/{world.theme}/completeness", headers=reader),
    ):
        assert (response.status_code, response.json()["code"]) == (403, "permission_denied")
    store.llm.reply = "[]"
    allowed = client.post(f"/themes/{world.theme}/completeness", headers=author)
    assert allowed.json() == {"uncovered_notions": []}
