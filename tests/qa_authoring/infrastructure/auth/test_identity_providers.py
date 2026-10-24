from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from qa_authoring.application.ports.identity import Identity, UnauthenticatedError
from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from qa_authoring.infrastructure.auth.entra import (
    EntraIdentityProvider,
    JwksSigningKeyResolver,
    entra_issuer,
    entra_jwks_uri,
)

TENANT = "11111111-2222-3333-4444-555555555555"
AUDIENCE = "api://qa-authoring"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
OID = "00000000-0000-0000-0000-0000000000a1"

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


async def test_dev_provider_reads_the_email_header() -> None:
    identity = await DevIdentityProvider().identify({"x-dev-user": " Ada@Example.org "})
    assert identity == Identity(email="Ada@Example.org", subject=None)


@pytest.mark.parametrize("headers", [{}, {"x-dev-user": "  "}])
async def test_dev_provider_requires_the_header(headers: dict[str, str]) -> None:
    with pytest.raises(UnauthenticatedError):
        await DevIdentityProvider().identify(headers)


class FixedKey:
    """Stands in for the JWKS lookup: always resolves the test signing key's public half."""

    def __init__(self) -> None:
        self.calls = 0

    def signing_key_for(self, token: str) -> Any:
        self.calls += 1
        return SIGNING_KEY.public_key()


def _token(key: Any = SIGNING_KEY, algorithm: str = "RS256", **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "oid": OID,
        "preferred_username": "Ada@Example.org",
        "email": "ada.alias@example.org",
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm=algorithm)


def _provider(resolver: FixedKey | None = None) -> EntraIdentityProvider:
    return EntraIdentityProvider(
        tenant=TENANT, audience=AUDIENCE, signing_key_resolver=resolver or FixedKey()
    )


def _bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


async def test_entra_provider_reads_email_and_oid() -> None:
    resolver = FixedKey()

    identity = await _provider(resolver).identify(_bearer(_token()))

    assert identity == Identity(email="Ada@Example.org", subject=OID)
    assert resolver.calls == 1


async def test_entra_provider_falls_back_to_the_email_claim() -> None:
    identity = await _provider().identify(_bearer(_token(preferred_username=None)))
    assert identity == Identity(email="ada.alias@example.org", subject=OID)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"authorization": ""},
        {"authorization": "Basic dXNlcjpwYXNz"},
        {"authorization": "Bearer "},
        {"authorization": "Bearer not-a-jwt"},
    ],
)
async def test_entra_provider_requires_a_bearer_token(headers: dict[str, str]) -> None:
    with pytest.raises(UnauthenticatedError):
        await _provider().identify(headers)


@pytest.mark.parametrize(
    "token",
    [
        _token(key=OTHER_KEY),
        _token(aud="api://someone-else"),
        _token(iss="https://login.microsoftonline.com/other-tenant/v2.0"),
        _token(iss="https://sts.windows.net/" + TENANT + "/"),
        _token(exp=int(time.time()) - 60),
        _token(exp=None),
        _token(oid=None),
        _token(oid=""),
        _token(preferred_username=None, email=None),
        _token(key="shared-secret-not-rsa-xxxxxxxxxxxxxxxx", algorithm="HS256"),
    ],
    ids=[
        "wrong-signature",
        "wrong-audience",
        "wrong-tenant",
        "v1-issuer",
        "expired",
        "no-expiry",
        "no-oid",
        "empty-oid",
        "no-email",
        "hs256",
    ],
)
async def test_entra_provider_rejects_invalid_tokens(token: str) -> None:
    with pytest.raises(UnauthenticatedError):
        await _provider().identify(_bearer(token))


def test_entra_provider_needs_an_audience_and_a_tenant() -> None:
    with pytest.raises(ValueError, match="audience"):
        EntraIdentityProvider(tenant=TENANT, audience="")
    with pytest.raises(ValueError, match="tenant"):
        EntraIdentityProvider(tenant="", audience=AUDIENCE)


def test_entra_endpoints_follow_the_tenant() -> None:
    assert entra_issuer(TENANT) == ISSUER
    assert entra_jwks_uri(TENANT) == (
        f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
    )


def test_default_resolver_reads_the_tenant_jwks_lazily() -> None:
    provider = EntraIdentityProvider(tenant=TENANT, audience=AUDIENCE)
    resolver = provider.signing_key_resolver
    assert isinstance(resolver, JwksSigningKeyResolver)
    assert resolver.jwks_uri == entra_jwks_uri(TENANT)
