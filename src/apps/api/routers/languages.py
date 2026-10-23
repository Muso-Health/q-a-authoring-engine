from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.dependencies import get_container
from apps.api.schemas.languages import (
    LanguageResponse,
    LanguagesResponse,
    RegisterLanguageRequest,
    UpdateLanguageRequest,
)
from config.container import Container
from qa_authoring.application.delete_language.command import DeleteLanguageCommand
from qa_authoring.application.get_language.command import GetLanguageQuery
from qa_authoring.application.list_languages.command import ListLanguagesQuery
from qa_authoring.application.register_language.command import RegisterLanguageCommand
from qa_authoring.application.update_language.command import UpdateLanguageCommand

router = APIRouter(prefix="/languages", tags=["languages"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_language(
    body: RegisterLanguageRequest, container: ContainerDep
) -> LanguageResponse:
    """Register a language. 409 if the code already exists; 422 if the code or name is invalid."""
    command = RegisterLanguageCommand(code=body.code, name=body.name)
    return LanguageResponse.of(await container.run(container.build_register_language, command))


@router.get("")
async def list_languages(container: ContainerDep) -> LanguagesResponse:
    """Every registered language, ordered by code."""
    return LanguagesResponse.of(
        await container.run(container.build_list_languages, ListLanguagesQuery())
    )


@router.get("/{language_id}")
async def get_language(language_id: UUID, container: ContainerDep) -> LanguageResponse:
    query = GetLanguageQuery(language_id=language_id)
    return LanguageResponse.of(await container.run(container.build_get_language, query))


@router.patch("/{language_id}")
async def update_language(
    language_id: UUID, body: UpdateLanguageRequest, container: ContainerDep
) -> LanguageResponse:
    """Rename a language. The code is immutable."""
    command = UpdateLanguageCommand(language_id=language_id, name=body.name)
    return LanguageResponse.of(await container.run(container.build_update_language, command))


@router.delete("/{language_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(language_id: UUID, container: ContainerDep) -> Response:
    await container.run(container.build_delete_language, DeleteLanguageCommand(language_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
