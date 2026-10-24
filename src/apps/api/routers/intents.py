from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import requires
from apps.api.dependencies import get_container
from apps.api.schemas.intents import IntentResponse, IntentsResponse, RegisterIntentRequest
from config.container import Container
from qa_authoring.application.delete_intent.command import DeleteIntentCommand
from qa_authoring.application.get_intent.command import GetIntentQuery
from qa_authoring.application.list_intents.command import ListIntentsQuery
from qa_authoring.application.register_intent.command import RegisterIntentCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(prefix="/intents", tags=["intents"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "", status_code=status.HTTP_201_CREATED, dependencies=[requires(Permission.MANAGE_INTENTS)]
)
async def register_intent(
    body: RegisterIntentRequest, response: Response, container: ContainerDep
) -> IntentResponse:
    """Get-or-create by normalized text (case and whitespace insensitive): 201 when created,
    200 with the existing intent otherwise."""
    command = RegisterIntentCommand(body.text)
    result, created = await container.run(container.build_register_intent, command)
    if not created:
        response.status_code = status.HTTP_200_OK
    return IntentResponse.of(result)


@router.get("")
async def list_intents(container: ContainerDep, q: str | None = None) -> IntentsResponse:
    """The catalogue ordered by normalized text; ``q`` keeps intents whose text starts with it."""
    query = ListIntentsQuery(prefix=q)
    return IntentsResponse.of(await container.run(container.build_list_intents, query))


@router.get("/{intent_id}")
async def get_intent(intent_id: UUID, container: ContainerDep) -> IntentResponse:
    query = GetIntentQuery(intent_id)
    return IntentResponse.of(await container.run(container.build_get_intent, query))


@router.delete(
    "/{intent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[requires(Permission.MANAGE_INTENTS)],
)
async def delete_intent(intent_id: UUID, container: ContainerDep) -> Response:
    """409 while any question variant has the intent attached."""
    await container.run(container.build_delete_intent, DeleteIntentCommand(intent_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
