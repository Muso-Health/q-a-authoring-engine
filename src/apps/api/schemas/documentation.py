from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qa_authoring.application.documentation_response import (
        CompletenessResult,
        DocumentationResult,
        DownloadUrlResult,
    )


class DocumentationResponse(BaseModel):
    id: UUID
    theme_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    @classmethod
    def of(cls, result: DocumentationResult) -> DocumentationResponse:
        return cls(
            id=result.id,
            theme_id=result.theme_id,
            filename=result.filename,
            mime_type=result.mime_type,
            size_bytes=result.size_bytes,
            checksum_sha256=result.checksum_sha256,
            created_at=result.created_at,
        )


class DocumentationListResponse(BaseModel):
    items: list[DocumentationResponse]

    @classmethod
    def of(cls, results: Sequence[DocumentationResult]) -> DocumentationListResponse:
        return cls(items=[DocumentationResponse.of(r) for r in results])


class DownloadUrlResponse(BaseModel):
    url: str
    expires_at: datetime

    @classmethod
    def of(cls, result: DownloadUrlResult) -> DownloadUrlResponse:
        return cls(url=result.url, expires_at=result.expires_at)


class CompletenessResponse(BaseModel):
    """Notions of the theme's documentation that no answer covers yet, in the base language."""

    uncovered_notions: list[str]

    @classmethod
    def of(cls, result: CompletenessResult) -> CompletenessResponse:
        return cls(uncovered_notions=list(result.uncovered_notions))
