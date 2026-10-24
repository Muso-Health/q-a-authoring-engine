from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from google.api_core.exceptions import NotFound

from qa_authoring.infrastructure.storage.gcs import GcsBlobStorage
from qa_authoring.infrastructure.storage.keys import object_key
from qa_authoring.infrastructure.storage.local import LocalBlobStorage

if TYPE_CHECKING:
    from pathlib import Path

SOUND = b"some recorded sound"
CHECKSUM = hashlib.sha256(SOUND).hexdigest()


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [("audio/", f"audio/{CHECKSUM}"), ("audio", f"audio/{CHECKSUM}"), ("", CHECKSUM)],
)
def test_object_key_is_derived_from_the_checksum(prefix: str, expected: str) -> None:
    assert object_key(prefix, SOUND) == expected


class FakeBlob:
    def __init__(self, bucket: FakeBucket, name: str) -> None:
        self.bucket = bucket
        self.name = name

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self.bucket.objects[self.name] = (data, content_type)

    def download_as_bytes(self) -> bytes:
        return self.bucket.objects[self.name][0]

    def delete(self) -> None:
        if self.name not in self.bucket.objects:
            raise NotFound("gone")  # type: ignore[no-untyped-call]
        del self.bucket.objects[self.name]

    def generate_signed_url(self, **kwargs: Any) -> str:
        self.bucket.signed.append((self.name, kwargs))
        return f"https://storage.example/{self.bucket.name}/{self.name}?signed"


class FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.signed: list[tuple[str, dict[str, Any]]] = []

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)


class FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket(name))


class TokenOnlyCredentials:
    """Like Cloud Run's metadata-server credentials: no private key, so signing goes via IAM."""

    service_account_email = "qa-app@project.iam.gserviceaccount.com"
    token = "access-token"

    def __init__(self) -> None:
        self.refreshed = False

    def refresh(self, request: Any) -> None:
        self.refreshed = True


class KeyCredentials:
    def sign_bytes(self, message: bytes) -> bytes:
        return b"signature"


async def test_gcs_store_uses_a_checksum_key_and_returns_a_gs_uri() -> None:
    client = FakeClient()
    storage = GcsBlobStorage(
        "qa-audio", "audio/", client_factory=lambda: (client, KeyCredentials())
    )

    uri = await storage.store(SOUND, "audio/webm")

    assert uri == f"gs://qa-audio/audio/{CHECKSUM}"
    assert client.buckets["qa-audio"].objects == {f"audio/{CHECKSUM}": (SOUND, "audio/webm")}
    assert await storage.store(SOUND, "audio/webm") == uri  # idempotent


async def test_gcs_delete_is_idempotent() -> None:
    client = FakeClient()
    storage = GcsBlobStorage(
        "qa-audio", "audio/", client_factory=lambda: (client, KeyCredentials())
    )
    uri = await storage.store(SOUND, "audio/webm")

    await storage.delete(uri)
    await storage.delete(uri)

    assert client.buckets["qa-audio"].objects == {}


async def test_gcs_signed_url_with_a_key() -> None:
    client = FakeClient()
    storage = GcsBlobStorage(
        "qa-audio", "audio/", client_factory=lambda: (client, KeyCredentials())
    )

    url = await storage.signed_url(f"gs://qa-audio/audio/{CHECKSUM}", 300)

    assert url == f"https://storage.example/qa-audio/audio/{CHECKSUM}?signed"
    [(name, kwargs)] = client.buckets["qa-audio"].signed
    assert name == f"audio/{CHECKSUM}"
    assert kwargs == {"version": "v4", "expiration": timedelta(seconds=300), "method": "GET"}


async def test_gcs_signed_url_without_a_key_signs_through_iam() -> None:
    client, credentials = FakeClient(), TokenOnlyCredentials()
    storage = GcsBlobStorage("qa-audio", "audio/", client_factory=lambda: (client, credentials))

    await storage.signed_url(f"gs://qa-audio/audio/{CHECKSUM}", 60)

    [(_, kwargs)] = client.buckets["qa-audio"].signed
    assert credentials.refreshed
    assert kwargs["service_account_email"] == "qa-app@project.iam.gserviceaccount.com"
    assert kwargs["access_token"] == "access-token"


async def test_gcs_rejects_a_uri_of_another_bucket() -> None:
    storage = GcsBlobStorage(
        "qa-audio", "audio/", client_factory=lambda: (FakeClient(), KeyCredentials())
    )
    with pytest.raises(ValueError, match="qa-audio"):
        await storage.delete("gs://other-bucket/audio/x")
    with pytest.raises(ValueError, match="gs://"):
        await storage.signed_url("file:///tmp/x", 60)


def test_gcs_requires_a_bucket() -> None:
    with pytest.raises(ValueError, match="bucket"):
        GcsBlobStorage("", "audio/")


async def test_local_storage_round_trip(tmp_path: Path) -> None:
    storage = LocalBlobStorage(tmp_path / "audio-store", "audio/")

    uri = await storage.store(SOUND, "audio/webm")

    path = tmp_path / "audio-store" / "audio" / CHECKSUM
    assert uri == path.as_uri()
    assert path.read_bytes() == SOUND
    assert await storage.signed_url(uri, 60) == uri
    await storage.delete(uri)
    await storage.delete(uri)
    assert not path.exists()


async def test_gcs_read() -> None:
    client = FakeClient()
    storage = GcsBlobStorage(
        "qa-docs", "documentation/", client_factory=lambda: (client, KeyCredentials())
    )
    uri = await storage.store(SOUND, "application/pdf")
    assert await storage.read(uri) == SOUND


async def test_local_read(tmp_path: Path) -> None:
    storage = LocalBlobStorage(tmp_path, "documentation/")
    assert await storage.read(await storage.store(SOUND, "text/plain")) == SOUND
