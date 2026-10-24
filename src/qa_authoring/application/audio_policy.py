from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioPolicy:
    """Upload limits and playback settings, from configuration."""

    max_upload_bytes: int
    allowed_mime_types: frozenset[str]
    playback_url_ttl_seconds: int
