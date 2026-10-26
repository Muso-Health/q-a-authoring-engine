from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, UploadFile, status

from apps.api.auth import requires, visible
from apps.api.dependencies import get_container
from apps.api.schemas.documentation import (
    CompletenessResponse,
    DocumentationListResponse,
    DocumentationResponse,
    DownloadUrlResponse,
)
from config.container import Container
from qa_authoring.application.analyze_theme_completeness.command import (
    AnalyzeThemeCompletenessQuery,
)
from qa_authoring.application.delete_documentation.command import DeleteDocumentationCommand
from qa_authoring.application.get_documentation_download_url.command import (
    GetDocumentationDownloadUrlQuery,
)
from qa_authoring.application.list_documentation.command import ListDocumentationQuery
from qa_authoring.application.ports.resource_scopes import ResourceKind
from qa_authoring.application.upload_documentation.command import UploadDocumentationCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["documentation"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "/themes/{theme_id}/documentation",
    status_code=status.HTTP_201_CREATED,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def upload_documentation(
    theme_id: UUID, file: UploadFile, container: ContainerDep
) -> DocumentationResponse:
    """Attach a document (multipart ``file``): PDF, Word, plain text, video or image."""
    content = await file.read(container.documentation_policy.max_upload_bytes + 1)
    command = UploadDocumentationCommand(
        theme_id, content, file.filename or "document", file.content_type
    )
    return DocumentationResponse.of(
        await container.run(container.build_upload_documentation, command)
    )


@router.get("/themes/{theme_id}/documentation", dependencies=[visible(ResourceKind.THEME)])
async def list_documentation(theme_id: UUID, container: ContainerDep) -> DocumentationListResponse:
    query = ListDocumentationQuery(theme_id)
    return DocumentationListResponse.of(
        await container.run(container.build_list_documentation, query)
    )


@router.delete(
    "/themes/{theme_id}/documentation/{documentation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def delete_documentation(
    theme_id: UUID, documentation_id: UUID, container: ContainerDep
) -> Response:
    command = DeleteDocumentationCommand(theme_id, documentation_id)
    await container.run(container.build_delete_documentation, command)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/documentation/{documentation_id}/download-url",
    dependencies=[visible(ResourceKind.DOCUMENTATION)],
)
async def get_documentation_download_url(
    documentation_id: UUID, container: ContainerDep
) -> DownloadUrlResponse:
    """A short-lived signed URL to download the document; mint a new one when it expires."""
    query = GetDocumentationDownloadUrlQuery(documentation_id)
    return DownloadUrlResponse.of(
        await container.run(container.build_get_documentation_download_url, query)
    )


@router.post(
    "/themes/{theme_id}/completeness",
    dependencies=[requires(Permission.AUTHOR_QASETS, on=ResourceKind.THEME)],
)
async def analyze_theme_completeness(
    theme_id: UUID, container: ContainerDep
) -> CompletenessResponse:
    """Which notions of the theme's documentation no answer covers, in the project's base
    language. Read-only. 409 if the theme has no documentation with readable text."""
    query = AnalyzeThemeCompletenessQuery(theme_id)
    return CompletenessResponse.of(
        await container.run(container.build_analyze_theme_completeness, query)
    )
