from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from qa_authoring.domain.model.permission import Permission
from tests.fakes import NOW, admin_client, in_memory_container, seed_user

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from tests.fakes import InMemoryStore

TERMS = "/glossary/terms"


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, InMemoryStore, dict[str, str]]]:
    container, store = in_memory_container()
    with admin_client(container, store) as client:
        fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        bm = _ok(client.post("/languages", json={"code": "bm", "name": "Bambara"}))["id"]
        yield client, store, {"fr": fr, "bm": bm}


def _ok(response: Any, status: int = 201) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


def _error(response: Any, status: int, code: str) -> Any:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code
    return body["details"]


def _create(client: TestClient, label: str, **body: Any) -> dict[str, Any]:
    return _ok(client.post(TERMS, json={"label": label, **body}))


def test_create_and_get(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, _, ids = setup
    created = _create(
        client,
        " malaria ",
        note="the disease",
        forms=[
            {
                "language_id": ids["fr"],
                "preferred": " paludisme ",
                "synonyms": ["palu", " palu ", ""],
                "avoid": ["malaria"],
            },
            {"language_id": ids["bm"], "preferred": "sumaya", "note": "spoken"},
        ],
    )

    stamp = NOW.isoformat().replace("+00:00", "Z")
    assert {k: v for k, v in created.items() if k != "forms"} == {
        "id": created["id"],
        "label": "malaria",
        "note": "the disease",
        "status": "active",
        "created_at": stamp,
        "updated_at": stamp,
    }
    forms = {f["language_id"]: f for f in created["forms"]}
    assert forms[ids["fr"]] == {
        "id": forms[ids["fr"]]["id"],
        "language_id": ids["fr"],
        "preferred": "paludisme",
        "synonyms": ["palu"],
        "avoid": ["malaria"],
        "note": None,
    }
    assert (forms[ids["bm"]]["synonyms"], forms[ids["bm"]]["note"]) == ([], "spoken")
    assert _ok(client.get(f"{TERMS}/{created['id']}"), 200) == created


def test_create_validation(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, store, ids = setup
    assert _error(client.post(TERMS, json={"label": " "}), 422, "invalid_glossary_field") == {
        "field": "label"
    }
    blank_form = {"label": "m", "forms": [{"language_id": ids["fr"], "preferred": ""}]}
    assert _error(client.post(TERMS, json=blank_form), 422, "invalid_glossary_field") == {
        "field": "preferred"
    }
    unknown = {"label": "m", "forms": [{"language_id": str(uuid4()), "preferred": "x"}]}
    _error(client.post(TERMS, json=unknown), 404, "language_not_found")
    details = _error(client.post(TERMS, json={"note": "n"}), 422, "invalid_request")
    assert details["errors"][0]["loc"] == ["body", "label"]
    _error(client.post(TERMS, json={"label": "m", "status": "archived"}), 422, "invalid_request")
    assert store.glossary.rows == {}


def test_patch_label_and_note(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, _, _ = setup
    term = _create(client, "malaria", note="n")
    url = f"{TERMS}/{term['id']}"

    relabeled = _ok(client.patch(url, json={"label": "Malaria"}), 200)
    cleared = _ok(client.patch(url, json={"note": None}), 200)

    assert (relabeled["label"], relabeled["note"]) == ("Malaria", "n")
    assert (cleared["label"], cleared["note"]) == ("Malaria", None)
    assert _error(client.patch(url, json={"label": "  "}), 422, "invalid_glossary_field") == {
        "field": "label"
    }
    _error(client.patch(url, json={"label": None}), 422, "invalid_request")
    _error(client.patch(f"{TERMS}/{uuid4()}", json={"label": "x"}), 404, "glossary_term_not_found")


def test_archive_and_unarchive(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, _, _ = setup
    term = _create(client, "malaria")
    url = f"{TERMS}/{term['id']}"

    assert _ok(client.post(f"{url}/archive"), 200)["status"] == "archived"
    assert _ok(client.post(f"{url}/archive"), 200)["status"] == "archived"
    assert _ok(client.post(f"{url}/unarchive"), 200)["status"] == "active"
    _error(client.post(f"{TERMS}/{uuid4()}/archive"), 404, "glossary_term_not_found")
    _error(client.post(f"{TERMS}/{uuid4()}/unarchive"), 404, "glossary_term_not_found")


def test_put_and_delete_a_form(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, _, ids = setup
    term = _create(client, "malaria")
    url = f"{TERMS}/{term['id']}/forms/{ids['fr']}"

    created = _ok(client.put(url, json={"preferred": "paludisme", "synonyms": ["palu"]}))
    replaced = _ok(client.put(url, json={"preferred": "malaria", "avoid": ["palu"]}), 200)

    [first] = created["forms"]
    [form] = replaced["forms"]
    assert form == {
        "id": first["id"],
        "language_id": ids["fr"],
        "preferred": "malaria",
        "synonyms": [],
        "avoid": ["palu"],
        "note": None,
    }

    assert client.delete(url).status_code == 204
    assert _ok(client.get(f"{TERMS}/{term['id']}"), 200)["forms"] == []
    _error(client.delete(url), 404, "glossary_form_not_found")


def test_form_errors(setup: tuple[TestClient, InMemoryStore, dict[str, str]]) -> None:
    client, _, ids = setup
    term = _create(client, "malaria")
    base = f"{TERMS}/{term['id']}/forms"

    assert _error(
        client.put(f"{base}/{ids['fr']}", json={"preferred": " "}), 422, "invalid_glossary_field"
    ) == {"field": "preferred"}
    _error(client.put(f"{base}/{ids['fr']}", json={}), 422, "invalid_request")
    _error(client.put(f"{base}/{uuid4()}", json={"preferred": "x"}), 404, "language_not_found")
    _error(
        client.put(f"{TERMS}/{uuid4()}/forms/{ids['fr']}", json={"preferred": "x"}),
        404,
        "glossary_term_not_found",
    )
    _error(client.delete(f"{TERMS}/{uuid4()}/forms/{ids['fr']}"), 404, "glossary_term_not_found")
    _error(client.get(f"{TERMS}/{uuid4()}"), 404, "glossary_term_not_found")
    _error(client.get(f"{TERMS}/not-a-uuid"), 422, "invalid_request")


def test_list_filters_searches_and_pages(
    setup: tuple[TestClient, InMemoryStore, dict[str, str]],
) -> None:
    client, _, ids = setup
    fr = ids["fr"]
    _create(client, "Malaria", forms=[{"language_id": fr, "preferred": "paludisme"}])
    _create(client, "fever", forms=[{"language_id": fr, "preferred": "fièvre"}])
    cough = _create(client, "cough")
    _ok(client.post(f"{TERMS}/{cough['id']}/archive"), 200)

    def labels(**params: Any) -> tuple[list[str], int]:
        page = _ok(client.get(TERMS, params=params), 200)
        return [t["label"] for t in page["items"]], page["total"]

    assert labels() == (["fever", "Malaria"], 2)
    assert labels(status="archived") == (["cough"], 1)
    assert labels(status="all") == (["cough", "fever", "Malaria"], 3)
    assert labels(q="FIEVRE") == (["fever"], 1)
    assert labels(status="all", limit=2, offset=2) == (["Malaria"], 3)
    page = _ok(client.get(TERMS, params={"q": "palud"}), 200)
    assert page["items"][0]["forms"][0]["preferred"] == "paludisme"
    for params in ({"status": "deleted"}, {"limit": 0}, {"limit": 201}, {"offset": -1}):
        _error(client.get(TERMS, params=params), 422, "invalid_request")


def test_reads_need_authentication_and_writes_need_manage_glossary(
    setup: tuple[TestClient, InMemoryStore, dict[str, str]],
) -> None:
    client, store, ids = setup
    term = _create(client, "malaria")
    url = f"{TERMS}/{term['id']}"
    # Every other permission, manage_categories included, is not enough to write.
    seed_user(
        store,
        "reader@example.org",
        *(p for p in Permission if p is not Permission.MANAGE_GLOSSARY),
    )
    seed_user(store, "nobody@example.org")
    seed_user(store, "editor@example.org", Permission.MANAGE_GLOSSARY)
    reader = {"X-Dev-User": "reader@example.org"}
    editor = {"X-Dev-User": "editor@example.org"}

    for headers in (reader, {"X-Dev-User": "nobody@example.org"}):
        assert client.get(TERMS, headers=headers).status_code == 200
        assert client.get(url, headers=headers).status_code == 200
    form_url = f"{url}/forms/{ids['fr']}"
    writes: list[tuple[str, str, dict[str, Any]]] = [
        ("post", TERMS, {"json": {"label": "fever"}}),
        ("patch", url, {"json": {"label": "Malaria"}}),
        ("post", f"{url}/archive", {}),
        ("post", f"{url}/unarchive", {}),
        ("put", form_url, {"json": {"preferred": "paludisme"}}),
        ("delete", form_url, {}),
    ]
    for method, path, kwargs in writes:
        denied = getattr(client, method)(path, headers=reader, **kwargs)
        _error(denied, 403, "permission_denied")
        allowed = getattr(client, method)(path, headers=editor, **kwargs)
        assert allowed.status_code in (200, 201, 204), (method, path, allowed.text)
