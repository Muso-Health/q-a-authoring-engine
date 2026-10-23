from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


class Container:
    """The DI container: wires use-case handlers over the adapters, built once per process.

    It owns nothing it did not receive — the engine is created (and disposed) by the engine factory
    in ``main.py``'s lifespan. Framework-agnostic: the API edge reads it off ``app.state``.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
