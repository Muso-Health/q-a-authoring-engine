from __future__ import annotations

from typing import Protocol


class ExportStoragePort(Protocol):
    """Where export files live. Content-addressed: the same bytes share one blob."""

    async def store(self, content: bytes, mime_type: str) -> str: ...

    async def signed_url(self, storage_uri: str, ttl_seconds: int) -> str: ...
