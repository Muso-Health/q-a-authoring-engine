from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from tests.fakes import admin_client, in_memory_container

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


def _upload(content: bytes, mime: str = "audio/webm") -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("recording.webm", content, mime)}


class World:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        fr = _ok(client.post("/languages", json={"code": "fr", "name": "French"}))["id"]
        project = _ok(client.post("/projects", json={"name": "P", "base_language_id": fr}))["id"]
        protocol = _ok(client.post(f"/projects/{project}/protocols", json={"name": "Pr"}))["id"]
        theme = _ok(client.post(f"/protocols/{protocol}/themes", json={"name": "T"}))["id"]
        qaset = _ok(
            client.post(f"/themes/{theme}/qasets", json={"language_id": fr, "answer_text": "a"})
        )
        self.qaset_id = qaset["id"]
        self.answer_id = qaset["languages"][0]["answer"]["id"]
        variant = _ok(
            client.post(f"/qasets/{self.qaset_id}/languages/{fr}/variants", json={"text": "q"})
        )
        self.variant_id = variant["id"]
        self.answer_url = f"/qasets/{self.qaset_id}/answers/{self.answer_id}/audio"
        self.variant_url = f"/qasets/{self.qaset_id}/variants/{self.variant_id}/audio"

    def presence(self) -> dict[str, Any]:
        presence: dict[str, Any] = _ok(self.client.get(f"/qasets/{self.qaset_id}"), 200)[
            "languages"
        ][0]
        return presence


@pytest.fixture
def world(setup: tuple[TestClient, InMemoryStore]) -> World:
    return World(setup[0])


def test_upload_answer_audio_and_read_it(
    setup: tuple[TestClient, InMemoryStore], world: World
) -> None:
    client, store = setup
    assert world.presence()["answer"]["audio"] is None

    body = _ok(client.post(world.answer_url, files=_upload(b"sound")))

    checksum = hashlib.sha256(b"sound").hexdigest()
    assert body == {
        "audio_id": body["audio_id"],
        "mime_type": "audio/webm",
        "duration_ms": 1500,
        "size_bytes": 5,
        "checksum_sha256": checksum,
        "created_at": "2026-10-24T12:00:00Z",
    }
    assert world.presence()["answer"]["audio"] == {
        "audio_id": body["audio_id"],
        "mime_type": "audio/webm",
        "duration_ms": 1500,
        "size_bytes": 5,
        "checksum_sha256": checksum,
        "audio_validation": None,
    }
    assert _ok(client.get(f"/audios/{body['audio_id']}"), 200) == body
    assert list(store.audio_storage.blobs) == [f"memory://audio/{checksum}"]


def test_replace_returns_200_and_a_new_audio(world: World) -> None:
    first = _ok(world.client.post(world.answer_url, files=_upload(b"first")))
    second = _ok(world.client.post(world.answer_url, files=_upload(b"second")), 200)
    assert second["audio_id"] != first["audio_id"]
    assert world.presence()["answer"]["audio"]["audio_id"] == second["audio_id"]
    _error(world.client.get(f"/audios/{first['audio_id']}"), 404, "audio_not_found")


def test_variant_audio_lifecycle(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, store = setup
    body = _ok(client.post(world.variant_url, files=_upload(b"variant sound")))
    assert world.presence()["variants"][0]["audio"]["audio_id"] == body["audio_id"]
    assert world.presence()["answer"]["audio"] is None

    response = client.delete(world.variant_url)

    assert response.status_code == 204
    assert world.presence()["variants"][0]["audio"] is None
    assert store.audio_storage.blobs == {}
    _error(client.delete(world.variant_url), 404, "audio_not_found")
    _error(client.delete(world.answer_url), 404, "audio_not_found")


def test_playback_url(world: World) -> None:
    body = _ok(world.client.post(world.answer_url, files=_upload(b"sound")))
    playback = _ok(world.client.get(f"/audios/{body['audio_id']}/playback-url"), 200)
    assert playback == {
        "url": f"https://signed.example/audio/{body['checksum_sha256']}?ttl=300",
        "expires_at": "2026-10-24T12:05:00Z",
    }
    _error(world.client.get(f"/audios/{uuid4()}/playback-url"), 404, "audio_not_found")


def test_validation_errors(setup: tuple[TestClient, InMemoryStore], world: World) -> None:
    client, store = setup
    _error(client.post(world.answer_url, files=_upload(b"x" * 65)), 422, "audio_too_large")
    _error(client.post(world.answer_url, files=_upload(b"junk")), 422, "unsupported_audio_type")
    store.audio_probe.mime_type = "audio/mpeg"
    _error(client.post(world.answer_url, files=_upload(b"mp3")), 422, "unsupported_audio_type")
    _error(client.post(world.answer_url), 422, "invalid_request")
    assert store.audio_storage.blobs == {}


def test_not_found_errors(world: World) -> None:
    client = world.client
    missing_qaset = f"/qasets/{uuid4()}/answers/{world.answer_id}/audio"
    _error(client.post(missing_qaset, files=_upload(b"s")), 404, "qaset_not_found")
    _error(
        client.post(f"/qasets/{world.qaset_id}/answers/{uuid4()}/audio", files=_upload(b"s")),
        404,
        "answer_not_found",
    )
    _error(
        client.post(f"/qasets/{world.qaset_id}/variants/{uuid4()}/audio", files=_upload(b"s")),
        404,
        "variant_not_found",
    )
    _error(
        client.delete(f"/qasets/{world.qaset_id}/answers/{uuid4()}/audio"), 404, "answer_not_found"
    )
    _error(client.get(f"/audios/{uuid4()}"), 404, "audio_not_found")
