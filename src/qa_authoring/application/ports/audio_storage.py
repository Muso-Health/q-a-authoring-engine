from __future__ import annotations

from typing import Protocol


class AudioStoragePort(Protocol):
    """Where recordings live. Keys are content-addressed, so storing the same bytes twice yields
    the same ``storage_uri`` and several references may share one blob."""

    async def store(self, content: bytes, mime_type: str) -> str:
        """Store the bytes and return their ``storage_uri``; idempotent."""
        ...

    async def delete(self, storage_uri: str) -> None:
        """Delete the blob; a missing blob is not an error."""
        ...

    async def signed_url(self, storage_uri: str, ttl_seconds: int) -> str:
        """A short-lived URL the browser can play the recording from."""
        ...
