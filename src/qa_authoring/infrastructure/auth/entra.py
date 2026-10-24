from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from qa_authoring.application.ports.identity import Identity, UnauthenticatedError

if TYPE_CHECKING:
    from collections.abc import Mapping

_AUTHORITY = "https://login.microsoftonline.com"


def entra_issuer(tenant: str) -> str:
    return f"{_AUTHORITY}/{tenant}/v2.0"


def entra_jwks_uri(tenant: str) -> str:
    return f"{_AUTHORITY}/{tenant}/discovery/v2.0/keys"


class SigningKeyResolver(Protocol):
    """Resolves the public key a token was signed with; tests supply a fixed key."""

    def signing_key_for(self, token: str) -> Any: ...


class JwksSigningKeyResolver:
    """Resolves signing keys from the tenant's published JWKS. ``PyJWKClient`` fetches lazily and
    caches the key set, so only a cold cache or a key rotation costs a network round-trip."""

    def __init__(self, jwks_uri: str) -> None:
        self.jwks_uri = jwks_uri
        self._client = PyJWKClient(jwks_uri)

    def signing_key_for(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


class EntraIdentityProvider:
    """Validates a Microsoft Entra ID v2 access token from the ``Authorization: Bearer`` header:
    RS256 signature against the tenant's keys, audience (the app's client id / application ID
    URI), the tenant's v2 issuer, and expiry. The email comes from ``preferred_username``
    (falling back to ``email``); the subject is the ``oid`` claim, Entra's stable object id,
    which is only ever stored and compared, never returned."""

    def __init__(
        self,
        *,
        tenant: str,
        audience: str,
        signing_key_resolver: SigningKeyResolver | None = None,
    ) -> None:
        if not audience:
            raise ValueError("the Entra audience is required (QA_AUTHORING_AUTH_ENTRA_AUDIENCE)")
        if not tenant:
            raise ValueError("the Entra tenant is required (QA_AUTHORING_AUTH_ENTRA_TENANT)")
        self._audience = audience
        self._issuer = entra_issuer(tenant)
        self.signing_key_resolver = signing_key_resolver or JwksSigningKeyResolver(
            entra_jwks_uri(tenant)
        )

    async def identify(self, headers: Mapping[str, str]) -> Identity:
        scheme, _, token = (headers.get("authorization") or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise UnauthenticatedError("missing bearer token")
        try:
            # Key resolution may touch the network (cold cache); keep it off the event loop.
            key = await asyncio.to_thread(self.signing_key_resolver.signing_key_for, token)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except (jwt.InvalidTokenError, PyJWKClientError) as exc:
            raise UnauthenticatedError("invalid bearer token") from exc
        email = _claim(claims, "preferred_username", "email")
        subject = _claim(claims, "oid")
        if email is None or subject is None:
            raise UnauthenticatedError("the token carries no email or object id")
        return Identity(email=email, subject=subject)


def _claim(claims: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
