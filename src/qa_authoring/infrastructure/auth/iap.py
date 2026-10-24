from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from qa_authoring.application.ports.identity import Identity, UnauthenticatedError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

IAP_ASSERTION_HEADER = "x-goog-iap-jwt-assertion"
IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"

type Verifier = Callable[[str, str], dict[str, Any]]


def _verify_with_google(assertion: str, audience: str) -> dict[str, Any]:
    from google.auth.transport import requests
    from google.oauth2 import id_token

    claims = id_token.verify_token(
        assertion, requests.Request(), audience=audience, certs_url=IAP_CERTS_URL
    )
    return dict(claims)


class IapIdentityProvider:
    """Verifies the signed assertion Google Identity-Aware Proxy adds to every request (signature,
    expiry, audience and issuer) and reads the email and subject from it."""

    def __init__(self, audience: str, verifier: Verifier = _verify_with_google) -> None:
        if not audience:
            raise ValueError("the IAP audience is required (QA_AUTHORING_AUTH_IAP_AUDIENCE)")
        self._audience = audience
        self._verifier = verifier

    async def identify(self, headers: Mapping[str, str]) -> Identity:
        assertion = headers.get(IAP_ASSERTION_HEADER)
        if not assertion:
            raise UnauthenticatedError(f"missing {IAP_ASSERTION_HEADER} header")
        try:
            claims = await asyncio.to_thread(self._verifier, assertion, self._audience)
        except ValueError as exc:
            raise UnauthenticatedError("invalid IAP assertion") from exc
        email, subject = claims.get("email"), claims.get("sub")
        if claims.get("iss", IAP_ISSUER) != IAP_ISSUER or not email or not subject:
            raise UnauthenticatedError("IAP assertion is missing its issuer, email or subject")
        return Identity(email=str(email), subject=str(subject))
