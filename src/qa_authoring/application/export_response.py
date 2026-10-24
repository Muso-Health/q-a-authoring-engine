from __future__ import annotations

from dataclasses import dataclass

from qa_authoring.application.documentation_response import (
    DownloadUrlResult,  # noqa: TC001 — a field type on frozen result dataclasses
)


@dataclass(frozen=True, slots=True)
class ExportCounts:
    qaset_count: int
    qa_row_count: int
    link_count: int


@dataclass(frozen=True, slots=True)
class ExportResult:
    qa_rows: DownloadUrlResult
    translation_links: DownloadUrlResult
    counts: ExportCounts
