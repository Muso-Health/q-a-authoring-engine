from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.dependencies import get_container
from apps.api.schemas.qasets import (
    AnswerInLanguageRequest,
    LanguagePresenceResponse,
    QASetResponse,
    QASetsResponse,
    QuestionVariantResponse,
    TextRequest,
)
from config.container import Container
from qa_authoring.application.add_language_presence.command import AddLanguagePresenceCommand
from qa_authoring.application.add_question_variant.command import AddQuestionVariantCommand
from qa_authoring.application.create_qaset.command import CreateQASetCommand
from qa_authoring.application.delete_qaset.command import DeleteQASetCommand
from qa_authoring.application.delete_question_variant.command import (
    DeleteQuestionVariantCommand,
)
from qa_authoring.application.get_qaset.command import GetQASetQuery
from qa_authoring.application.list_qasets.command import ListQASetsQuery
from qa_authoring.application.remove_language_presence.command import (
    RemoveLanguagePresenceCommand,
)
from qa_authoring.application.update_answer.command import UpdateAnswerCommand
from qa_authoring.application.update_question_variant.command import (
    UpdateQuestionVariantCommand,
)

router = APIRouter(tags=["qasets"])

ContainerDep = Annotated[Container, Depends(get_container)]


def _no_content() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/themes/{theme_id}/qasets", status_code=status.HTTP_201_CREATED)
async def create_qaset(
    theme_id: UUID, body: AnswerInLanguageRequest, container: ContainerDep
) -> QASetResponse:
    """Create a QA set with its first answer. 404 if the theme is unknown, 422 if the language."""
    command = CreateQASetCommand(
        theme_id=theme_id, language_id=body.language_id, answer_text=body.answer_text
    )
    return QASetResponse.of(await container.run(container.build_create_qaset, command))


@router.get("/themes/{theme_id}/qasets")
async def list_qasets(theme_id: UUID, container: ContainerDep) -> QASetsResponse:
    query = ListQASetsQuery(theme_id)
    return QASetsResponse.of(await container.run(container.build_list_qasets, query))


@router.get("/qasets/{qaset_id}")
async def get_qaset(qaset_id: UUID, container: ContainerDep) -> QASetResponse:
    """The QA set grouped by language: each language's answer, variants and variant count."""
    query = GetQASetQuery(qaset_id)
    return QASetResponse.of(await container.run(container.build_get_qaset, query))


@router.delete("/qasets/{qaset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_qaset(qaset_id: UUID, container: ContainerDep) -> Response:
    """Deletes the QA set together with its answers and question variants."""
    await container.run(container.build_delete_qaset, DeleteQASetCommand(qaset_id))
    return _no_content()


@router.post("/qasets/{qaset_id}/languages", status_code=status.HTTP_201_CREATED)
async def add_language_presence(
    qaset_id: UUID, body: AnswerInLanguageRequest, container: ContainerDep
) -> LanguagePresenceResponse:
    """Add a language by giving its answer. 409 if the language already has one."""
    command = AddLanguagePresenceCommand(
        qaset_id=qaset_id, language_id=body.language_id, answer_text=body.answer_text
    )
    result = await container.run(container.build_add_language_presence, command)
    return LanguagePresenceResponse.of(result)


@router.patch("/qasets/{qaset_id}/languages/{language_id}")
async def update_answer(
    qaset_id: UUID, language_id: UUID, body: TextRequest, container: ContainerDep
) -> LanguagePresenceResponse:
    """Edit the answer text in a language present in the QA set."""
    command = UpdateAnswerCommand(qaset_id=qaset_id, language_id=language_id, text=body.text)
    return LanguagePresenceResponse.of(await container.run(container.build_update_answer, command))


@router.delete("/qasets/{qaset_id}/languages/{language_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_language_presence(
    qaset_id: UUID, language_id: UUID, container: ContainerDep
) -> Response:
    """Remove a language's answer and all its question variants."""
    command = RemoveLanguagePresenceCommand(qaset_id=qaset_id, language_id=language_id)
    await container.run(container.build_remove_language_presence, command)
    return _no_content()


@router.post(
    "/qasets/{qaset_id}/languages/{language_id}/variants", status_code=status.HTTP_201_CREATED
)
async def add_question_variant(
    qaset_id: UUID, language_id: UUID, body: TextRequest, container: ContainerDep
) -> QuestionVariantResponse:
    """409 if the language has no answer in this QA set yet."""
    command = AddQuestionVariantCommand(qaset_id=qaset_id, language_id=language_id, text=body.text)
    result = await container.run(container.build_add_question_variant, command)
    return QuestionVariantResponse.of(result)


@router.patch("/qasets/{qaset_id}/variants/{variant_id}")
async def update_question_variant(
    qaset_id: UUID, variant_id: UUID, body: TextRequest, container: ContainerDep
) -> QuestionVariantResponse:
    command = UpdateQuestionVariantCommand(qaset_id=qaset_id, variant_id=variant_id, text=body.text)
    result = await container.run(container.build_update_question_variant, command)
    return QuestionVariantResponse.of(result)


@router.delete("/qasets/{qaset_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question_variant(
    qaset_id: UUID, variant_id: UUID, container: ContainerDep
) -> Response:
    command = DeleteQuestionVariantCommand(qaset_id=qaset_id, variant_id=variant_id)
    await container.run(container.build_delete_question_variant, command)
    return _no_content()
