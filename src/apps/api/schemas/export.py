from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from apps.api.schemas.documentation import DownloadUrlResponse

if TYPE_CHECKING:
    from qa_authoring.application.export_response import ExportResult


class ExportCountsResponse(BaseModel):
    qaset_count: int
    qa_row_count: int
    link_count: int


class ExportResponse(BaseModel):
    """Short-lived signed URLs to the Parquet files, and what they contain."""

    qa_rows: DownloadUrlResponse
    translation_links: DownloadUrlResponse
    counts: ExportCountsResponse

    @classmethod
    def of(cls, result: ExportResult) -> ExportResponse:
        counts = result.counts
        return cls(
            qa_rows=DownloadUrlResponse.of(result.qa_rows),
            translation_links=DownloadUrlResponse.of(result.translation_links),
            counts=ExportCountsResponse(
                qaset_count=counts.qaset_count,
                qa_row_count=counts.qa_row_count,
                link_count=counts.link_count,
            ),
        )
