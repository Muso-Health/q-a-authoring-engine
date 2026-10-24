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


class World:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.fr, self.bm = _language(client, "fr"), _language(client, "bm")
        project = _ok(client.post("/projects", json={"name": "P", "base_language_id": self.fr}))
        protocol = _ok(client.post(f"/projects/{project['id']}/protocols", json={"name": "Pr"}))
        theme = _ok(client.post(f"/protocols/{protocol['id']}/themes", json={"name": "T"}))
        qaset = _ok(
            client.post(
                f"/themes/{theme['id']}/qasets",
                json={"language_id": self.fr, "answer_text": "fr answer"},
            )
        )
        self.qaset_id = qaset["id"]
        self.fr_answer = qaset["languages"][0]["answer"]["id"]
        bm = _ok(
            client.post(
                f"/qasets/{self.qaset_id}/languages",
                json={"language_id": self.bm, "answer_text": "bm answer"},
            )
        )
        self.bm_answer = bm["answer"]["id"]
        self.fr_variant = self._variant(self.fr, "fr q")
        self.bm_variant = self._variant(self.bm, "bm q1")
        self.bm_variant_2 = self._variant(self.bm, "bm q2")

    def _variant(self, language_id: str, text: str) -> str:
        url = f"/qasets/{self.qaset_id}/languages/{language_id}/variants"
        return str(_ok(self.client.post(url, json={"text": text}))["id"])

    def read(self) -> dict[str, Any]:
        return _ok(self.client.get(f"/qasets/{self.qaset_id}"), 200)

    def answer(self, language_id: str) -> dict[str, Any]:
        [presence] = [p for p in self.read()["languages"] if p["language_id"] == language_id]
        answer: dict[str, Any] = presence["answer"]
        return answer

    def variant(self, variant_id: str) -> dict[str, Any]:
        variants: list[dict[str, Any]] = [
            v for p in self.read()["languages"] for v in p["variants"] if v["id"] == variant_id
        ]
        assert len(variants) == 1
        return variants[0]


@pytest.fixture
def world(client: TestClient) -> World:
    return World(client)


def test_answer_link_appears_on_both_sides(client: TestClient, world: World) -> None:
    link = _ok(
        client.post(
            f"/qasets/{world.qaset_id}/answer-links",
            json={"answer_a_id": world.bm_answer, "answer_b_id": world.fr_answer},
        )
    )
    assert set(link) == {"id", "answer_ids"}
    assert sorted(link["answer_ids"]) == link["answer_ids"]
    assert set(link["answer_ids"]) == {world.fr_answer, world.bm_answer}

    assert world.answer(world.fr)["links"] == [
        {"link_id": link["id"], "other_id": world.bm_answer, "other_language_id": world.bm}
    ]
    assert world.answer(world.bm)["links"] == [
        {"link_id": link["id"], "other_id": world.fr_answer, "other_language_id": world.fr}
    ]

    response = client.delete(f"/qasets/{world.qaset_id}/answer-links/{link['id']}")
    assert response.status_code == 204
    assert world.answer(world.fr)["links"] == []
    assert world.answer(world.bm)["links"] == []


def test_variant_links_form_a_free_graph(client: TestClient, world: World) -> None:
    url = f"/qasets/{world.qaset_id}/variant-links"
    first = _ok(
        client.post(url, json={"variant_a_id": world.fr_variant, "variant_b_id": world.bm_variant})
    )
    second = _ok(
        client.post(
            url, json={"variant_a_id": world.bm_variant_2, "variant_b_id": world.fr_variant}
        )
    )
    assert set(first) == {"id", "variant_ids"}

    assert [link["other_id"] for link in world.variant(world.fr_variant)["links"]] == [
        world.bm_variant,
        world.bm_variant_2,
    ]
    assert world.variant(world.bm_variant_2)["links"] == [
        {"link_id": second["id"], "other_id": world.fr_variant, "other_language_id": world.fr}
    ]

    assert client.delete(f"{url}/{first['id']}").status_code == 204
    assert [link["link_id"] for link in world.variant(world.fr_variant)["links"]] == [second["id"]]
    assert world.variant(world.bm_variant)["links"] == []


def test_answers_carry_empty_links_by_default(world: World) -> None:
    assert world.answer(world.fr)["links"] == []
    assert world.variant(world.fr_variant)["links"] == []


def test_link_errors(client: TestClient, world: World) -> None:
    answers = f"/qasets/{world.qaset_id}/answer-links"
    variants = f"/qasets/{world.qaset_id}/variant-links"

    def answer_pair(a: str, b: str) -> dict[str, str]:
        return {"answer_a_id": a, "answer_b_id": b}

    def variant_pair(a: str, b: str) -> dict[str, str]:
        return {"variant_a_id": a, "variant_b_id": b}

    _error(
        client.post(answers, json=answer_pair(world.fr_answer, world.fr_answer)), 422, "self_link"
    )
    _error(
        client.post(variants, json=variant_pair(world.bm_variant, world.bm_variant_2)),
        422,
        "same_language",
    )
    _error(
        client.post(answers, json=answer_pair(world.fr_answer, str(uuid4()))),
        404,
        "answer_not_found",
    )
    _error(
        client.post(variants, json=variant_pair(world.fr_variant, world.fr_answer)),
        404,
        "variant_not_found",
    )
    _error(client.post(answers, json={"answer_a_id": world.fr_answer}), 422, "invalid_request")

    _ok(client.post(answers, json=answer_pair(world.fr_answer, world.bm_answer)))
    _error(
        client.post(answers, json=answer_pair(world.bm_answer, world.fr_answer)),
        409,
        "link_already_exists",
    )

    _error(client.delete(f"{answers}/{uuid4()}"), 404, "link_not_found")
    _error(client.delete(f"{variants}/{uuid4()}"), 404, "link_not_found")
    missing = f"/qasets/{uuid4()}"
    _error(
        client.post(f"{missing}/answer-links", json=answer_pair(world.fr_answer, world.bm_answer)),
        404,
        "qaset_not_found",
    )
    _error(client.delete(f"{missing}/variant-links/{uuid4()}"), 404, "qaset_not_found")


def test_removing_a_language_presence_drops_its_links(client: TestClient, world: World) -> None:
    _ok(
        client.post(
            f"/qasets/{world.qaset_id}/answer-links",
            json={"answer_a_id": world.fr_answer, "answer_b_id": world.bm_answer},
        )
    )
    _ok(
        client.post(
            f"/qasets/{world.qaset_id}/variant-links",
            json={"variant_a_id": world.fr_variant, "variant_b_id": world.bm_variant},
        )
    )

    assert client.delete(f"/qasets/{world.qaset_id}/languages/{world.bm}").status_code == 204

    assert world.answer(world.fr)["links"] == []
    assert world.variant(world.fr_variant)["links"] == []
