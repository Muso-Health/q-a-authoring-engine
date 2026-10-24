from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, status

from apps.api.auth import CurrentUser, requires
from apps.api.dependencies import get_container
from apps.api.schemas.translation import (
    TranslatedAnswerResponse,
    TranslatedVariantResponse,
    TranslateRequest,
)
from config.container import Container
from qa_authoring.application.translate_answer.command import TranslateAnswerCommand
from qa_authoring.application.translate_variant.command import TranslateVariantCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["translation"], dependencies=[requires(Permission.AUTHOR_QASETS)])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "/qasets/{qaset_id}/answers/{answer_id}/translate", status_code=status.HTTP_201_CREATED
)
async def translate_answer(
    qaset_id: UUID,
    answer_id: UUID,
    body: TranslateRequest,
    user: CurrentUser,
    container: ContainerDep,
) -> TranslatedAnswerResponse:
    """Translate the answer into a language the QA set lacks, with the chosen engine: creates
    that language's answer and links it to the source. 502 if the engine fails (nothing saved)."""
    command = TranslateAnswerCommand(
        qaset_id, answer_id, body.target_language_id, body.engine, actor_user_id=user.id
    )
    return TranslatedAnswerResponse.of(
        await container.run(container.build_translate_answer, command)
    )


@router.post(
    "/qasets/{qaset_id}/variants/{variant_id}/translate", status_code=status.HTTP_201_CREATED
)
async def translate_variant(
    qaset_id: UUID,
    variant_id: UUID,
    body: TranslateRequest,
    user: CurrentUser,
    container: ContainerDep,
) -> TranslatedVariantResponse:
    """Translate the question variant into a language that already has an answer in the QA set:
    creates the variant and links it to the source. 409 if the target has no answer yet."""
    command = TranslateVariantCommand(
        qaset_id, variant_id, body.target_language_id, body.engine, actor_user_id=user.id
    )
    return TranslatedVariantResponse.of(
        await container.run(container.build_translate_variant, command)
    )
