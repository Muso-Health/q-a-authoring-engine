from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pyarrow.parquet as pq
import pytest

from qa_authoring.domain.model.permission import Permission
from tests.fakes import EXPORT_URL_TTL_SECONDS, admin_client, in_memory_container, seed_user

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
    assert response.json()["code"] == code


class World:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        self.bm = _ok(client.post("/languages", json={"code": "bm", "name": "Bambara"}))["id"]
        self.project = _ok(
            client.post("/projects", json={"name": "P", "base_language_id": self.fr})
        )["id"]
        protocol = _ok(client.post(f"/projects/{self.project}/protocols", json={"name": "Pr"}))
        self.theme = _ok(client.post(f"/protocols/{protocol['id']}/themes", json={"name": "T"}))[
            "id"
        ]
        self.url = f"/projects/{self.project}/export"

    def qaset(self, decision: str | None) -> dict[str, Any]:
        # A theme holds each base-language answer once.
        answer = f"Buvez de l'eau ({uuid4().hex[:8]})."
        body = {"language_id": self.fr, "answer_text": answer}
        qaset = _ok(self.client.post(f"/themes/{self.theme}/qasets", json=body))
        base = f"/qasets/{qaset['id']}/languages"
        fr_variant = _ok(self.client.post(f"{base}/{self.fr}/variants", json={"text": "Boire ?"}))
        _ok(self.client.post(base, json={"language_id": self.bm, "answer_text": "Ji min."}))
        bm_variant = _ok(self.client.post(f"{base}/{self.bm}/variants", json={"text": "Ji?"}))
        link = {"variant_a_id": fr_variant["id"], "variant_b_id": bm_variant["id"]}
        _ok(self.client.post(f"/qasets/{qaset['id']}/variant-links", json=link))
        if decision is not None:
            url = f"/qasets/{qaset['id']}/clinical-validation"
            _ok(self.client.post(url, json={"decision": decision}))
        return qaset


@pytest.fixture
def world(setup: tuple[TestClient, InMemoryStore]) -> World:
    return World(setup[0])


def test_exports_the_validated_corpus(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    client, store = setup
    validated = world.qaset("validated")
    world.qaset("rejected")
    world.qaset(None)

    body = _ok(client.post(world.url), 200)

    assert body["counts"] == {"qaset_count": 1, "qa_row_count": 2, "link_count": 1}
    assert set(body) == {"qa_rows", "translation_links", "counts"}
    for name in ("qa_rows", "translation_links"):
        assert body[name]["url"].startswith("https://signed.example/exports/")
        assert body[name]["url"].endswith(f"?ttl={EXPORT_URL_TTL_SECONDS}")
        assert body[name]["expires_at"] == "2026-10-24T12:15:00Z"
    qa_rows_uri = "memory://" + body["qa_rows"]["url"].split("signed.example/")[1].split("?")[0]
    rows = pq.read_table(io.BytesIO(store.export_storage.blobs[qa_rows_uri])).to_pylist()
    assert {row["qaset_id"] for row in rows} == {validated["id"]}
    assert {row["language_code"] for row in rows} == {"fr", "bm"}


def test_errors(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, _ = setup
    _error(client.post(world.url), 409, "nothing_to_export")
    world.qaset("rejected")
    _error(client.post(world.url), 409, "nothing_to_export")
    _error(client.post(f"/projects/{uuid4()}/export"), 404, "project_not_found")


def test_needs_export_corpus(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, store = setup
    world.qaset("validated")
    seed_user(
        store, "without@example.org", *[p for p in Permission if p is not Permission.EXPORT_CORPUS]
    )
    seed_user(store, "exporter@example.org", Permission.EXPORT_CORPUS)

    denied = client.post(world.url, headers={"X-Dev-User": "without@example.org"})
    allowed = client.post(world.url, headers={"X-Dev-User": "exporter@example.org"})

    assert (denied.status_code, denied.json()["code"]) == (403, "permission_denied")
    assert allowed.status_code == 200, allowed.text
