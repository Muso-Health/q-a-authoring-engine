from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — FastAPI resolves path parameter annotations at runtime

from fastapi import APIRouter, Depends, Response, status

from apps.api.auth import requires, visible
from apps.api.dependencies import get_container
from apps.api.schemas.catalog import (
    CreateNamedRequest,
    ThemeResponse,
    ThemesResponse,
    UpdateNamedRequest,
)
from config.container import Container
from qa_authoring.application.create_theme.command import CreateThemeCommand
from qa_authoring.application.delete_theme.command import DeleteThemeCommand
from qa_authoring.application.get_theme.command import GetThemeQuery
from qa_authoring.application.list_themes.command import ListThemesQuery
from qa_authoring.application.ports.resource_scopes import ResourceKind
from qa_authoring.application.update_theme.command import UpdateThemeCommand
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["themes"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "/protocols/{protocol_id}/themes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def create_theme(
    protocol_id: UUID, body: CreateNamedRequest, container: ContainerDep
) -> ThemeResponse:
    """Create a theme under a protocol. 404 if the protocol does not exist."""
    command = CreateThemeCommand(
        protocol_id=protocol_id, name=body.name, description=body.description
    )
    return ThemeResponse.of(await container.run(container.build_create_theme, command))


@router.get("/protocols/{protocol_id}/themes", dependencies=[visible(ResourceKind.PROTOCOL)])
async def list_themes(protocol_id: UUID, container: ContainerDep) -> ThemesResponse:
    query = ListThemesQuery(protocol_id)
    return ThemesResponse.of(await container.run(container.build_list_themes, query))


@router.get("/themes/{theme_id}", dependencies=[visible(ResourceKind.THEME)])
async def get_theme(theme_id: UUID, container: ContainerDep) -> ThemeResponse:
    query = GetThemeQuery(theme_id)
    return ThemeResponse.of(await container.run(container.build_get_theme, query))


@router.patch("/themes/{theme_id}", dependencies=[requires(Permission.MANAGE_CATALOG)])
async def update_theme(
    theme_id: UUID, body: UpdateNamedRequest, container: ContainerDep
) -> ThemeResponse:
    command = UpdateThemeCommand(theme_id, name=body.name, description=body.description_change())
    return ThemeResponse.of(await container.run(container.build_update_theme, command))


@router.delete(
    "/themes/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[requires(Permission.MANAGE_CATALOG)],
)
async def delete_theme(theme_id: UUID, container: ContainerDep) -> Response:
    await container.run(container.build_delete_theme, DeleteThemeCommand(theme_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
