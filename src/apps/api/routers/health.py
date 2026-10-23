from __future__ import annotations

from fastapi import APIRouter

from apps.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> HealthResponse:
    """Liveness: the process is up and serving. Deliberately touches no database."""
    return HealthResponse()
