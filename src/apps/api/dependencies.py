from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002 — FastAPI resolves this annotation at runtime

if TYPE_CHECKING:
    from config.container import Container


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container
