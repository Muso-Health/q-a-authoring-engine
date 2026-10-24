from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import unquote, urlparse

from qa_authoring.infrastructure.storage.keys import object_key


class LocalBlobStorage:
    """A blob storage port on the local filesystem, for development and tests. URIs are
    ``file://`` URIs and the "signed" URL is the URI itself: nothing is served or signed."""

    def __init__(self, directory: Path, prefix: str) -> None:
        self._directory = directory.resolve()
        self._prefix = prefix

    async def store(self, content: bytes, mime_type: str) -> str:
        path = self._directory / object_key(self._prefix, content)
        await asyncio.to_thread(self._write, path, content)
        return path.as_uri()

    async def read(self, storage_uri: str) -> bytes:
        return await asyncio.to_thread(self._path(storage_uri).read_bytes)

    async def delete(self, storage_uri: str) -> None:
        await asyncio.to_thread(self._path(storage_uri).unlink, missing_ok=True)

    async def signed_url(self, storage_uri: str, ttl_seconds: int) -> str:
        return storage_uri

    def _path(self, storage_uri: str) -> Path:
        path = Path(unquote(urlparse(storage_uri).path)).resolve()
        if not path.is_relative_to(self._directory):
            raise ValueError(f"{storage_uri!r} is outside the storage directory")
        return path

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
