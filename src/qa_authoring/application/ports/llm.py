from __future__ import annotations

from typing import Protocol


class LlmUnavailableError(Exception):
    """The model could not produce an answer (unconfigured, unreachable, refused, empty)."""


class LlmPort(Protocol):
    """A provider-agnostic text model; which provider backs it is deployment configuration."""

    async def generate(self, prompt: str) -> str:
        """The model's text answer to ``prompt``; raises ``LlmUnavailableError``."""
        ...
