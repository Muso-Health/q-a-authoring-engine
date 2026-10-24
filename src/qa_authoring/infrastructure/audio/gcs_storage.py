from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from google.api_core.exceptions import NotFound

from qa_authoring.infrastructure.audio.keys import object_key

if TYPE_CHECKING:
    from collections.abc import Callable

_SCHEME = "gs://"


def _default_client() -> tuple[Any, Any]:
    import google.auth
    from google.cloud import storage  # type: ignore[attr-defined]

    credentials, project = google.auth.default()
    return storage.Client(credentials=credentials, project=project), credentials


class GcsAudioStorage:
    """The audio storage port on Google Cloud Storage: ``gs://<bucket>/<prefix><sha256>``.

    The client is built lazily (first call), so the app starts without credentials; blocking
    calls run in a thread. Signed URLs are V4 GET URLs. Credentials without a private key (Cloud
    Run's metadata server) sign through the IAM signBlob API, which needs the service account to
    hold ``roles/iam.serviceAccountTokenCreator`` on itself.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str,
        client_factory: Callable[[], tuple[Any, Any]] = _default_client,
    ) -> None:
        if not bucket:
            raise ValueError("an audio bucket is required for GCS storage")
        self._bucket = bucket
        self._prefix = prefix
        self._client_factory = client_factory
        self._client: Any = None
        self._credentials: Any = None

    async def store(self, content: bytes, mime_type: str) -> str:
        key = object_key(self._prefix, content)
        await asyncio.to_thread(self._upload, key, content, mime_type)
        return f"{_SCHEME}{self._bucket}/{key}"

    async def delete(self, storage_uri: str) -> None:
        await asyncio.to_thread(self._delete, self._key(storage_uri))

    async def signed_url(self, storage_uri: str, ttl_seconds: int) -> str:
        return await asyncio.to_thread(self._sign, self._key(storage_uri), ttl_seconds)

    def _key(self, storage_uri: str) -> str:
        if not storage_uri.startswith(_SCHEME):
            raise ValueError(f"not a gs:// URI: {storage_uri!r}")
        bucket, _, key = storage_uri.removeprefix(_SCHEME).partition("/")
        if bucket != self._bucket:
            raise ValueError(f"{storage_uri!r} is not in bucket {self._bucket!r}")
        return key

    def _blob(self, key: str) -> Any:
        if self._client is None:
            self._client, self._credentials = self._client_factory()
        return self._client.bucket(self._bucket).blob(key)

    def _upload(self, key: str, content: bytes, mime_type: str) -> None:
        self._blob(key).upload_from_string(content, content_type=mime_type)

    def _delete(self, key: str) -> None:
        with contextlib.suppress(NotFound):
            self._blob(key).delete()

    def _sign(self, key: str, ttl_seconds: int) -> str:
        blob = self._blob(key)
        kwargs: dict[str, Any] = {}
        if not hasattr(self._credentials, "sign_bytes"):
            from google.auth.transport.requests import Request

            self._credentials.refresh(Request())
            kwargs = {
                "service_account_email": self._credentials.service_account_email,
                "access_token": self._credentials.token,
            }
        url: str = blob.generate_signed_url(
            version="v4", expiration=timedelta(seconds=ttl_seconds), method="GET", **kwargs
        )
        return url
