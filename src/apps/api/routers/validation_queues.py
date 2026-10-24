from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves query parameter annotations at runtime

from fastapi import APIRouter, Depends

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.validation_queues import (
    AudioQueueResponse,
    ClinicalQueueResponse,
    TranslationQueueResponse,
)
from config.container import Container
from qa_authoring.application.list_validation_queues.command import ValidationQueueQuery
from qa_authoring.domain.model.permission import Permission

router = APIRouter(prefix="/validation-queues", tags=["validation queues"])

ContainerDep = Annotated[Container, Depends(get_container)]


def _query(
    project_id: UUID | None = None,
    theme_id: UUID | None = None,
    state: str = "pending",
    limit: int = 50,
    cursor: str | None = None,
) -> ValidationQueueQuery:
    """``state``: pending (default; includes never decided), rejected, validated or all.
    Items are ordered by id; pass the previous page's ``next_cursor`` to continue."""
    return ValidationQueueQuery(project_id, theme_id, state, limit, cursor)


QueryDep = Annotated[ValidationQueueQuery, Depends(_query)]


@router.get("/clinical", dependencies=[requires(Permission.VALIDATE_CLINICAL)])
async def clinical_queue(query: QueryDep, container: ContainerDep) -> ClinicalQueueResponse:
    """QA sets with a base-language answer, with that answer and its question variants."""
    return ClinicalQueueResponse.of(await container.run(container.build_list_clinical_queue, query))


@router.get("/translation", dependencies=[requires(Permission.VALIDATE_TRANSLATION)])
async def translation_queue(query: QueryDep, container: ContainerDep) -> TranslationQueueResponse:
    """Translated answers and question variants, with the base-language text they translate."""
    return TranslationQueueResponse.of(
        await container.run(container.build_list_translation_queue, query)
    )


@router.get("/audio", dependencies=[requires(Permission.VALIDATE_AUDIO)])
async def audio_queue(query: QueryDep, container: ContainerDep) -> AudioQueueResponse:
    """Recordings, with the answer or question variant they voice."""
    return AudioQueueResponse.of(await container.run(container.build_list_audio_queue, query))
