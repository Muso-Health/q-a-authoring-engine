from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import CurrentUser, requires
from apps.api.dependencies import get_container
from apps.api.schemas.validation import DecisionRequest, ValidationResponse
from config.container import Container
from qa_authoring.application.get_audio_validation.command import GetAudioValidationQuery
from qa_authoring.application.get_clinical_validation.command import GetClinicalValidationQuery
from qa_authoring.application.get_translation_validation.command import (
    GetTranslationValidationQuery,
)
from qa_authoring.application.ports.resource_scopes import ResourceKind
from qa_authoring.application.record_audio_decision.command import RecordAudioDecisionCommand
from qa_authoring.application.record_clinical_decision.command import (
    RecordClinicalDecisionCommand,
)
from qa_authoring.application.record_translation_decision.command import (
    RecordTranslationDecisionCommand,
)
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["validation"])

ContainerDep = Annotated[Container, Depends(get_container)]
CLINICAL = [requires(Permission.VALIDATE_CLINICAL, on=ResourceKind.QASET)]
ANSWER_TRANSLATION = [requires(Permission.VALIDATE_TRANSLATION, on=ResourceKind.ANSWER)]
VARIANT_TRANSLATION = [requires(Permission.VALIDATE_TRANSLATION, on=ResourceKind.VARIANT)]
AUDIO = [requires(Permission.VALIDATE_AUDIO, on=ResourceKind.AUDIO)]


def _respond(response: Response, created: bool) -> None:
    if not created:
        response.status_code = status.HTTP_200_OK


@router.post(
    "/qasets/{qaset_id}/clinical-validation",
    status_code=status.HTTP_201_CREATED,
    dependencies=CLINICAL,
)
async def record_clinical_decision(
    qaset_id: UUID,
    body: DecisionRequest,
    user: CurrentUser,
    response: Response,
    container: ContainerDep,
) -> ValidationResponse:
    """Record a clinical decision (201 the first time, 200 after). 409 if the QA set has no
    answer in its project's base language."""
    command = RecordClinicalDecisionCommand(
        qaset_id, body.decision, actor_user_id=user.id, note=body.note
    )
    result, created = await container.run(container.build_record_clinical_decision, command)
    _respond(response, created)
    return ValidationResponse.of(result)


@router.get("/qasets/{qaset_id}/clinical-validation", dependencies=CLINICAL)
async def get_clinical_validation(qaset_id: UUID, container: ContainerDep) -> ValidationResponse:
    query = GetClinicalValidationQuery(qaset_id)
    return ValidationResponse.of(
        await container.run(container.build_get_clinical_validation, query)
    )


async def _record_translation(
    container: Container,
    response: Response,
    command: RecordTranslationDecisionCommand,
) -> ValidationResponse:
    result, created = await container.run(container.build_record_translation_decision, command)
    _respond(response, created)
    return ValidationResponse.of(result)


@router.post(
    "/answers/{answer_id}/translation-validation",
    status_code=status.HTTP_201_CREATED,
    dependencies=ANSWER_TRANSLATION,
)
async def record_answer_translation_decision(
    answer_id: UUID,
    body: DecisionRequest,
    user: CurrentUser,
    response: Response,
    container: ContainerDep,
) -> ValidationResponse:
    """422 ``not_a_translation`` for an answer in the project's base language."""
    command = RecordTranslationDecisionCommand(
        body.decision, actor_user_id=user.id, answer_id=answer_id, note=body.note
    )
    return await _record_translation(container, response, command)


@router.get("/answers/{answer_id}/translation-validation", dependencies=ANSWER_TRANSLATION)
async def get_answer_translation_validation(
    answer_id: UUID, container: ContainerDep
) -> ValidationResponse:
    query = GetTranslationValidationQuery(answer_id=answer_id)
    return ValidationResponse.of(
        await container.run(container.build_get_translation_validation, query)
    )


@router.post(
    "/variants/{variant_id}/translation-validation",
    status_code=status.HTTP_201_CREATED,
    dependencies=VARIANT_TRANSLATION,
)
async def record_variant_translation_decision(
    variant_id: UUID,
    body: DecisionRequest,
    user: CurrentUser,
    response: Response,
    container: ContainerDep,
) -> ValidationResponse:
    """422 ``not_a_translation`` for a variant in the project's base language."""
    command = RecordTranslationDecisionCommand(
        body.decision, actor_user_id=user.id, variant_id=variant_id, note=body.note
    )
    return await _record_translation(container, response, command)


@router.get("/variants/{variant_id}/translation-validation", dependencies=VARIANT_TRANSLATION)
async def get_variant_translation_validation(
    variant_id: UUID, container: ContainerDep
) -> ValidationResponse:
    query = GetTranslationValidationQuery(variant_id=variant_id)
    return ValidationResponse.of(
        await container.run(container.build_get_translation_validation, query)
    )


@router.post(
    "/audios/{audio_id}/audio-validation",
    status_code=status.HTTP_201_CREATED,
    dependencies=AUDIO,
)
async def record_audio_decision(
    audio_id: UUID,
    body: DecisionRequest,
    user: CurrentUser,
    response: Response,
    container: ContainerDep,
) -> ValidationResponse:
    command = RecordAudioDecisionCommand(
        audio_id, body.decision, actor_user_id=user.id, note=body.note
    )
    result, created = await container.run(container.build_record_audio_decision, command)
    _respond(response, created)
    return ValidationResponse.of(result)


@router.get("/audios/{audio_id}/audio-validation", dependencies=AUDIO)
async def get_audio_validation(audio_id: UUID, container: ContainerDep) -> ValidationResponse:
    query = GetAudioValidationQuery(audio_id)
    return ValidationResponse.of(await container.run(container.build_get_audio_validation, query))
