from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentationPolicy:
    max_upload_bytes: int
    allowed_mime_types: frozenset[str]
    download_url_ttl_seconds: int


def normalize_mime(mime_type: str | None) -> str:
    """``Application/PDF; charset=binary`` -> ``application/pdf``."""
    return (mime_type or "").split(";")[0].strip().lower()
