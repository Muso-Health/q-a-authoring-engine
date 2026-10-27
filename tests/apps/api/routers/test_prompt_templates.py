from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from qa_authoring.domain.model.permission import Permission
from qa_authoring.domain.model.prompt_template import (
    DEFAULT_TEMPLATES,
    PromptTemplate,
    PromptTemplateKey,
)
from tests.fakes import ADMIN_EMAIL, NOW, admin_client, in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from tests.fakes import InMemoryStore

TRANSLATION = "Translate {text} from {source_language} into {target_language}. {glossary}"


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryStore]]:
    container, store = in_memory_container()
    with admin_client(container, store) as client:
        for key in PromptTemplateKey:
            store.prompt_templates.rows[key] = PromptTemplate.create(
                key, DEFAULT_TEMPLATES[key], updated_by=None, at=NOW
            )
        yield client, store


def _ok(response: Any, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


def _error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code
    return body


def test_list_and_get_the_seeded_defaults(setup: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = setup
    items = _ok(client.get("/prompt-templates"))["items"]
    assert [item["key"] for item in items] == ["completeness", "translation", "variant_generation"]

    translation = _ok(client.get("/prompt-templates/translation"))
    assert translation == {
        "key": "translation",
        "content": DEFAULT_TEMPLATES[PromptTemplateKey.TRANSLATION],
        "required_placeholders": ["glossary", "source_language", "target_language", "text"],
        "updated_by": None,
        "updated_at": "2026-10-24T12:00:00Z",
    }


def test_put_updates_and_shows_the_editor_email(setup: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = setup
    updated = _ok(client.put("/prompt-templates/translation", json={"content": TRANSLATION}))
    assert (updated["content"], updated["updated_by"]) == (TRANSLATION, ADMIN_EMAIL)
    assert _ok(client.get("/prompt-templates/translation")) == updated
    assert set(updated) == {
        "key",
        "content",
        "required_placeholders",
        "updated_by",
        "updated_at",
    }


def test_invalid_templates_are_422_with_the_placeholders(
    setup: tuple[TestClient, InMemoryStore],
) -> None:
    client, _ = setup
    body = _error(
        client.put("/prompt-templates/translation", json={"content": "{text} in {tone}"}),
        422,
        "invalid_prompt_template",
    )
    assert body["details"] == {
        "missing": ["glossary", "source_language", "target_language"],
        "unknown": ["tone"],
    }
    _error(
        client.put("/prompt-templates/translation", json={"content": TRANSLATION + " {text.x}"}),
        422,
        "invalid_prompt_template",
    )
    _error(client.put("/prompt-templates/translation", json={}), 422, "invalid_request")


def test_unknown_keys_are_404(setup: tuple[TestClient, InMemoryStore]) -> None:
    client, _ = setup
    _error(client.get("/prompt-templates/summary"), 404, "prompt_template_not_found")
    _error(
        client.put("/prompt-templates/summary", json={"content": TRANSLATION}),
        404,
        "prompt_template_not_found",
    )


def test_editing_needs_manage_prompts_but_reading_does_not(
    setup: tuple[TestClient, InMemoryStore],
) -> None:
    client, store = setup
    seed_user(store, "reader@example.org")
    seed_user(
        store, "author@example.org", *[p for p in Permission if p is not Permission.MANAGE_PROMPTS]
    )
    seed_user(store, "prompter@example.org", Permission.MANAGE_PROMPTS)

    assert (
        client.get("/prompt-templates", headers={"X-Dev-User": "reader@example.org"}).status_code
        == 200
    )
    assert (
        client.get(
            "/prompt-templates/translation", headers={"X-Dev-User": "reader@example.org"}
        ).status_code
        == 200
    )
    denied = client.put(
        "/prompt-templates/translation",
        json={"content": TRANSLATION},
        headers={"X-Dev-User": "author@example.org"},
    )
    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
    allowed = client.put(
        "/prompt-templates/translation",
        json={"content": TRANSLATION},
        headers={"X-Dev-User": "prompter@example.org"},
    )
    assert (allowed.status_code, allowed.json()["updated_by"]) == (200, "prompter@example.org")
