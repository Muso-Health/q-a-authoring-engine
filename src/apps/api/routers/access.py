from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.auth import CurrentUser  # noqa: TC001 — FastAPI resolves this annotation at runtime
from apps.api.dependencies import get_container
from apps.api.schemas.access import MeResponse, PermissionsResponse
from config.container import Container
from qa_authoring.application.get_user.command import GetUserQuery
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["access"])

ContainerDep = Annotated[Container, Depends(get_container)]


@router.get("/me")
async def me(user: CurrentUser, container: ContainerDep) -> MeResponse:
    profile = await container.run(container.build_get_user, GetUserQuery(user.id))
    return MeResponse.of(user, profile)


@router.get("/permissions")
async def list_permissions() -> PermissionsResponse:
    """The fixed permission catalogue roles are built from."""
    return PermissionsResponse(items=sorted(p.value for p in Permission))
