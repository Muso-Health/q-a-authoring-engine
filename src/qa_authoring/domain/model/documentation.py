from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — a field type on a frozen dataclass
from uuid import UUID, uuid4

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_MIME_TYPE = re.compile(r"[a-z0-9.+-]+/[a-z0-9.+-]+")
_MAX_FILENAME = 255


class InvalidDocumentationError(ValueError):
    """Raised when documentation metadata is malformed."""


def clean_filename(filename: str) -> str:
    """The file's own name: no directories (either separator), trimmed, never empty."""
    name = re.split(r"[\\/]", filename)[-1].strip()
    return name[-_MAX_FILENAME:] or "document"


@dataclass(frozen=True, slots=True)
class Documentation:
    """A reference document attached to a theme; the bytes live in storage, not here."""

    id: UUID
    theme_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    storage_uri: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not _MIME_TYPE.fullmatch(self.mime_type):
            raise InvalidDocumentationError(f"invalid mime type {self.mime_type!r}")
        if self.size_bytes <= 0:
            raise InvalidDocumentationError("size_bytes must be positive")
        if not _SHA256_HEX.fullmatch(self.checksum_sha256):
            raise InvalidDocumentationError("checksum_sha256 must be 64 lowercase hex digits")
        if not self.storage_uri:
            raise InvalidDocumentationError("storage_uri must not be empty")
        if not self.filename or self.filename != clean_filename(self.filename):
            raise InvalidDocumentationError(f"invalid file name {self.filename!r}")
        if self.created_at.tzinfo is None:
            raise InvalidDocumentationError("created_at must be timezone-aware")

    @classmethod
    def create(
        cls,
        *,
        theme_id: UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        checksum_sha256: str,
        storage_uri: str,
        at: datetime,
    ) -> Documentation:
        return cls(
            id=uuid4(),
            theme_id=theme_id,
            filename=clean_filename(filename),
            mime_type=mime_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            storage_uri=storage_uri,
            created_at=at,
        )
