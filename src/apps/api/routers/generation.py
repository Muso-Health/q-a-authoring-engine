from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.generation import GeneratedVariantsResponse, GenerateVariantsRequest
from config.container import Container
from qa_authoring.application.generate_variants.command import GenerateVariantsQuery
from qa_authoring.application.ports.resource_scopes import ResourceKind
from qa_authoring.domain.model.permission import Permission

router = APIRouter(
    tags=["generation"],
    dependencies=[requires(Permission.AUTHOR_QASETS, on=ResourceKind.QASET)],
)

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post("/qasets/{qaset_id}/answers/{answer_id}/generate-variants")
async def generate_variants(
    qaset_id: UUID, answer_id: UUID, body: GenerateVariantsRequest, container: ContainerDep
) -> GeneratedVariantsResponse:
    """Propose question variants in the answer's language. Nothing is saved: keep the chosen
    ones through ``POST /qasets/{id}/languages/{language_id}/variants``."""
    query = GenerateVariantsQuery(qaset_id, answer_id, body.context)
    return GeneratedVariantsResponse.of(
        await container.run(container.build_generate_variants, query)
    )
