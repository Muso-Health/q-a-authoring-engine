from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from tests.fakes import admin_client, in_memory_container

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


def _language(client: TestClient, code: str) -> str:
    return str(_ok(client.post("/languages", json={"code": code, "name": code}))["id"])


def _theme(client: TestClient) -> tuple[str, str]:
    fr = _language(client, "fr")
    project = _ok(client.post("/projects", json={"name": "P", "base_language_id": fr}))["id"]
    protocol = _ok(client.post(f"/projects/{project}/protocols", json={"name": "Pr"}))["id"]
    theme = _ok(client.post(f"/protocols/{protocol}/themes", json={"name": "T"}))["id"]
    return str(theme), fr


def _qaset(client: TestClient, theme_id: str, language_id: str) -> dict[str, Any]:
    return _ok(
        client.post(
            f"/themes/{theme_id}/qasets",
            json={"language_id": language_id, "answer_text": " Rest. "},
        )
    )


@pytest.fixture
def setup(client: TestClient) -> tuple[str, str, str]:
    theme_id, fr = _theme(client)
    return theme_id, fr, str(_qaset(client, theme_id, fr)["id"])


def _presence(qaset: dict[str, Any], language_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = [
        p for p in qaset["languages"] if p["language_id"] == language_id
    ]
    assert len(matches) == 1
    return matches[0]


# --- create / read / delete ---


def test_create_qaset(client: TestClient) -> None:
    theme_id, fr = _theme(client)
    body = _qaset(client, theme_id, fr)
    assert body["theme_id"] == theme_id
    [presence] = body["languages"]
    assert presence["language_id"] == fr
    assert presence["answer"]["text"] == "Rest."
    assert set(presence["answer"]) == {"id", "text", "links", "audio", "translation_validation"}
    assert presence["answer"]["audio"] is None
    assert presence["answer"]["links"] == []
    assert presence["variants"] == []
    assert presence["variant_count"] == 0
    assert _ok(client.get(f"/qasets/{body['id']}"), 200) == body


def test_create_qaset_with_an_answer_the_theme_already_has_is_409(client: TestClient) -> None:
    theme_id, fr = _theme(client)
    existing = _qaset(client, theme_id, fr)
    response = client.post(
        f"/themes/{theme_id}/qasets", json={"language_id": fr, "answer_text": "Rest."}
    )
    _error(response, 409, "answer_already_exists")
    assert response.json()["details"] == {"qaset_id": existing["id"]}
    other = client.post(
        f"/themes/{theme_id}/qasets", json={"language_id": fr, "answer_text": "Drink."}
    )
    assert other.status_code == 201, other.text


def test_create_qaset_under_missing_theme_is_404(client: TestClient) -> None:
    fr = _language(client, "fr")
    response = client.post(
        f"/themes/{uuid4()}/qasets", json={"language_id": fr, "answer_text": "x"}
    )
    _error(response, 404, "theme_not_found")


def test_create_qaset_validation(client: TestClient) -> None:
    theme_id, fr = _theme(client)
    url = f"/themes/{theme_id}/qasets"
    unknown = str(uuid4())
    _error(
        client.post(url, json={"language_id": unknown, "answer_text": "x"}), 422, "unknown_language"
    )
    _error(client.post(url, json={"language_id": fr, "answer_text": " "}), 422, "invalid_text")
    _error(
        client.post(url, json={"language_id": fr, "answer_text": "x", "extra": 1}),
        422,
        "invalid_request",
    )
    _error(client.post(url, json={}), 422, "invalid_request")


def test_list_qasets_by_theme(client: TestClient) -> None:
    theme_id, fr = _theme(client)
    bm = _language(client, "bm")
    first = _qaset(client, theme_id, fr)["id"]
    _ok(client.post(f"/qasets/{first}/languages", json={"language_id": bm, "answer_text": "b"}))
    _ok(client.post(f"/qasets/{first}/languages/{bm}/variants", json={"text": "q"}))
    second = _qaset(client, theme_id, bm)["id"]

    items = _ok(client.get(f"/themes/{theme_id}/qasets"), 200)["items"]

    summary = {
        item["id"]: {lang["language_id"]: lang["variant_count"] for lang in item["languages"]}
        for item in items
    }
    assert summary == {first: {fr: 0, bm: 1}, second: {bm: 0}}
    assert all(item["theme_id"] == theme_id for item in items)


def test_list_qasets_of_missing_theme_is_404(client: TestClient) -> None:
    _error(client.get(f"/themes/{uuid4()}/qasets"), 404, "theme_not_found")


def test_delete_qaset(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, fr, qaset_id = setup
    _ok(client.post(f"/qasets/{qaset_id}/languages/{fr}/variants", json={"text": "q"}))
    response = client.delete(f"/qasets/{qaset_id}")
    assert response.status_code == 204
    assert response.content == b""
    _error(client.get(f"/qasets/{qaset_id}"), 404, "qaset_not_found")


def test_unknown_qaset_is_404(client: TestClient) -> None:
    url = f"/qasets/{uuid4()}"
    fr = _language(client, "fr")
    _error(client.get(url), 404, "qaset_not_found")
    _error(client.delete(url), 404, "qaset_not_found")
    _error(
        client.post(f"{url}/languages", json={"language_id": fr, "answer_text": "x"}),
        404,
        "qaset_not_found",
    )
    _error(client.patch(f"{url}/languages/{fr}", json={"text": "x"}), 404, "qaset_not_found")
    _error(
        client.post(f"{url}/languages/{fr}/variants", json={"text": "x"}), 404, "qaset_not_found"
    )
    _error(client.patch(f"{url}/variants/{uuid4()}", json={"text": "x"}), 404, "qaset_not_found")
    assert client.get("/qasets/not-a-uuid").status_code == 422


def test_delete_theme_with_qasets_is_409(client: TestClient, setup: tuple[str, str, str]) -> None:
    theme_id, _, _ = setup
    _error(client.delete(f"/themes/{theme_id}"), 409, "theme_has_qasets")


def test_delete_language_used_by_qaset_is_409(client: TestClient) -> None:
    theme_id, _ = _theme(client)
    bm = _language(client, "bm")
    _qaset(client, theme_id, bm)
    _error(client.delete(f"/languages/{bm}"), 409, "language_in_use")


# --- language presences ---


def test_add_update_remove_language_presence(
    client: TestClient, setup: tuple[str, str, str]
) -> None:
    _, fr, qaset_id = setup
    bm = _language(client, "bm")

    added = _ok(
        client.post(f"/qasets/{qaset_id}/languages", json={"language_id": bm, "answer_text": "b"})
    )
    assert (added["language_id"], added["answer"]["text"], added["variant_count"]) == (bm, "b", 0)

    patched = _ok(client.patch(f"/qasets/{qaset_id}/languages/{bm}", json={"text": " B2 "}), 200)
    assert patched["answer"]["text"] == "B2"
    assert patched["answer"]["id"] == added["answer"]["id"]

    _ok(client.post(f"/qasets/{qaset_id}/languages/{bm}/variants", json={"text": "q"}))
    assert client.delete(f"/qasets/{qaset_id}/languages/{bm}").status_code == 204

    qaset = _ok(client.get(f"/qasets/{qaset_id}"), 200)
    assert [p["language_id"] for p in qaset["languages"]] == [fr]


def test_add_present_language_is_409(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, fr, qaset_id = setup
    response = client.post(
        f"/qasets/{qaset_id}/languages", json={"language_id": fr, "answer_text": "again"}
    )
    _error(response, 409, "language_already_present")


def test_add_unknown_language_is_422(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, _, qaset_id = setup
    response = client.post(
        f"/qasets/{qaset_id}/languages", json={"language_id": str(uuid4()), "answer_text": "x"}
    )
    _error(response, 422, "unknown_language")


def test_absent_language_presence_is_404(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, _, qaset_id = setup
    bm = _language(client, "bm")
    _error(
        client.patch(f"/qasets/{qaset_id}/languages/{bm}", json={"text": "x"}),
        404,
        "language_not_present",
    )
    _error(client.delete(f"/qasets/{qaset_id}/languages/{bm}"), 404, "language_not_present")


def test_renaming_onto_another_sets_answer_is_409(
    client: TestClient, setup: tuple[str, str, str]
) -> None:
    theme_id, fr, rest = setup
    body = {"language_id": fr, "answer_text": "Drink."}
    drink = _ok(client.post(f"/themes/{theme_id}/qasets", json=body))["id"]
    url = f"/qasets/{drink}/languages/{fr}"
    response = client.patch(url, json={"text": "Rest."})
    _error(response, 409, "answer_already_exists")
    assert response.json()["details"] == {"qaset_id": rest}
    assert _ok(client.patch(url, json={"text": "Drink."}), 200)["answer"]["text"] == "Drink."
    assert _ok(client.patch(url, json={"text": "Sleep."}), 200)["answer"]["text"] == "Sleep."


def test_update_answer_validation(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, fr, qaset_id = setup
    url = f"/qasets/{qaset_id}/languages/{fr}"
    _error(client.patch(url, json={"text": "  "}), 422, "invalid_text")
    _error(client.patch(url, json={"language_id": str(uuid4())}), 422, "invalid_request")


# --- variants ---


@pytest.mark.usefixtures("descending_uuids")
def test_get_lists_languages_and_variants_in_creation_order(
    client: TestClient, setup: tuple[str, str, str]
) -> None:
    _, fr, qaset_id = setup
    bm = _language(client, "bm")
    _ok(client.post(f"/qasets/{qaset_id}/languages", json={"language_id": bm, "answer_text": "b"}))
    texts = ["first", "second", "third"]
    for text in texts:
        _ok(client.post(f"/qasets/{qaset_id}/languages/{fr}/variants", json={"text": text}))

    body = _ok(client.get(f"/qasets/{qaset_id}"), 200)

    assert [p["language_id"] for p in body["languages"]] == [fr, bm]
    assert [v["text"] for v in _presence(body, fr)["variants"]] == texts


def test_variant_lifecycle(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, fr, qaset_id = setup

    created = _ok(
        client.post(f"/qasets/{qaset_id}/languages/{fr}/variants", json={"text": " What? "})
    )
    assert created == {
        "id": created["id"],
        "language_id": fr,
        "text": "What?",
        "links": [],
        "intents": [],
        "audio": None,
        "translation_validation": None,
    }
    url = f"/qasets/{qaset_id}/variants/{created['id']}"

    patched = _ok(client.patch(url, json={"text": "What now?"}), 200)
    assert patched == {**created, "text": "What now?"}

    presence = _presence(_ok(client.get(f"/qasets/{qaset_id}"), 200), fr)
    assert presence["variant_count"] == 1
    assert presence["variants"] == [patched]

    assert client.delete(url).status_code == 204
    assert _presence(_ok(client.get(f"/qasets/{qaset_id}"), 200), fr)["variant_count"] == 0


def test_variant_for_absent_language_is_409(
    client: TestClient, setup: tuple[str, str, str]
) -> None:
    _, _, qaset_id = setup
    bm = _language(client, "bm")
    response = client.post(f"/qasets/{qaset_id}/languages/{bm}/variants", json={"text": "q"})
    _error(response, 409, "language_presence_required")


def test_unknown_variant_is_404(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, _, qaset_id = setup
    url = f"/qasets/{qaset_id}/variants/{uuid4()}"
    _error(client.patch(url, json={"text": "x"}), 404, "variant_not_found")
    _error(client.delete(url), 404, "variant_not_found")


def test_variant_validation(client: TestClient, setup: tuple[str, str, str]) -> None:
    _, fr, qaset_id = setup
    _error(
        client.post(f"/qasets/{qaset_id}/languages/{fr}/variants", json={"text": ""}),
        422,
        "invalid_text",
    )
    variant = _ok(client.post(f"/qasets/{qaset_id}/languages/{fr}/variants", json={"text": "q"}))
    _error(
        client.patch(
            f"/qasets/{qaset_id}/variants/{variant['id']}", json={"text": "q", "language_id": fr}
        ),
        422,
        "invalid_request",
    )
