from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 — a field type on frozen result dataclasses
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — a field type on frozen result dataclasses

if TYPE_CHECKING:
    from qa_authoring.domain.model.documentation import Documentation


@dataclass(frozen=True, slots=True)
class DocumentationResult:
    id: UUID
    theme_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    @classmethod
    def of(cls, documentation: Documentation) -> DocumentationResult:
        return cls(
            documentation.id,
            documentation.theme_id,
            documentation.filename,
            documentation.mime_type,
            documentation.size_bytes,
            documentation.checksum_sha256,
            documentation.created_at,
        )


@dataclass(frozen=True, slots=True)
class DownloadUrlResult:
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CompletenessResult:
    uncovered_notions: tuple[str, ...]
