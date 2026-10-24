from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


class UnauthenticatedError(Exception):
    """Raised when a request carries no valid identity."""


@dataclass(frozen=True, slots=True)
class Identity:
    """Who the identity provider says the caller is."""

    email: str
    subject: str | None


class IdentityProvider(Protocol):
    async def identify(self, headers: Mapping[str, str]) -> Identity:
        """The caller's identity from the request headers; raises ``UnauthenticatedError``."""
        ...
