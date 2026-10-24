from __future__ import annotations

from fastapi import APIRouter

from apps.api.auth import CurrentUser  # noqa: TC001 — FastAPI resolves this annotation at runtime
from apps.api.schemas.access import MeResponse, PermissionsResponse
from qa_authoring.domain.model.permission import Permission

router = APIRouter(tags=["access"])


@router.get("/me")
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse.of(user)


@router.get("/permissions")
async def list_permissions() -> PermissionsResponse:
    """The fixed permission catalogue roles are built from."""
    return PermissionsResponse(items=sorted(p.value for p in Permission))
