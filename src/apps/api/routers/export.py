from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.export import ExportResponse
from config.container import Container
from qa_authoring.application.export_project_corpus.command import ExportProjectCorpusCommand
from qa_authoring.application.ports.resource_scopes import ResourceKind
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["export"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "/projects/{project_id}/export",
    dependencies=[requires(Permission.EXPORT_CORPUS, on=ResourceKind.PROJECT)],
)
async def export_project_corpus(project_id: UUID, container: ContainerDep) -> ExportResponse:
    """Export the project's clinically validated QA sets, in every language, as two Parquet
    files: ``qa_rows`` (one row per question variant) and ``translation_links``. Read-only.
    409 if no QA set is clinically validated."""
    command = ExportProjectCorpusCommand(project_id)
    return ExportResponse.of(await container.run(container.build_export_project_corpus, command))
