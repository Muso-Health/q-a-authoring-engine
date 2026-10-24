from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.application.ports.identity import Identity, UnauthenticatedError

if TYPE_CHECKING:
    from collections.abc import Mapping

DEV_USER_HEADER = "x-dev-user"


class DevIdentityProvider:
    """Trusts the email in the ``X-Dev-User`` header. Local development and tests only: anyone
    can claim any identity with it."""

    async def identify(self, headers: Mapping[str, str]) -> Identity:
        email = (headers.get(DEV_USER_HEADER) or "").strip()
        if not email:
            raise UnauthenticatedError(f"missing {DEV_USER_HEADER} header")
        return Identity(email=email, subject=None)
