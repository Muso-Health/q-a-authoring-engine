from __future__ import annotations

from typing import Protocol


class DocumentStoragePort(Protocol):
    """Where documentation files live. Content-addressed: the same bytes share one blob."""

    async def store(self, content: bytes, mime_type: str) -> str: ...

    async def read(self, storage_uri: str) -> bytes: ...

    async def delete(self, storage_uri: str) -> None:
        """A missing blob is not an error."""
        ...

    async def signed_url(self, storage_uri: str, ttl_seconds: int) -> str: ...
