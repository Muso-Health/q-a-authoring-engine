from __future__ import annotations

from typing import Any

import pytest

from qa_authoring.application.ports.identity import Identity, UnauthenticatedError
from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from qa_authoring.infrastructure.auth.iap import IAP_ASSERTION_HEADER, IapIdentityProvider


async def test_dev_provider_reads_the_email_header() -> None:
    identity = await DevIdentityProvider().identify({"x-dev-user": " Ada@Example.org "})
    assert identity == Identity(email="Ada@Example.org", subject=None)


@pytest.mark.parametrize("headers", [{}, {"x-dev-user": "  "}])
async def test_dev_provider_requires_the_header(headers: dict[str, str]) -> None:
    with pytest.raises(UnauthenticatedError):
        await DevIdentityProvider().identify(headers)


class StubVerifier:
    """Stands in for Google's signature check; returns the claims or raises like the real one."""

    def __init__(
        self, claims: dict[str, Any] | None = None, error: Exception | None = None
    ) -> None:
        self.claims = claims or {}
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def __call__(self, assertion: str, audience: str) -> dict[str, Any]:
        self.calls.append((assertion, audience))
        if self.error is not None:
            raise self.error
        return self.claims


async def test_iap_provider_extracts_email_and_subject() -> None:
    verifier = StubVerifier(
        {
            "email": "ada@example.org",
            "sub": "accounts.google.com:123",
            "iss": "https://cloud.google.com/iap",
        }
    )
    provider = IapIdentityProvider("/projects/1/global/backendServices/2", verifier=verifier)

    identity = await provider.identify({IAP_ASSERTION_HEADER: "signed.jwt.token"})

    assert identity == Identity(email="ada@example.org", subject="accounts.google.com:123")
    assert verifier.calls == [("signed.jwt.token", "/projects/1/global/backendServices/2")]


@pytest.mark.parametrize(
    ("headers", "verifier"),
    [
        ({}, StubVerifier({"email": "a@b.c", "sub": "s"})),
        ({IAP_ASSERTION_HEADER: "x"}, StubVerifier(error=ValueError("bad signature"))),
        ({IAP_ASSERTION_HEADER: "x"}, StubVerifier({"sub": "s"})),
        ({IAP_ASSERTION_HEADER: "x"}, StubVerifier({"email": "a@b.c"})),
        (
            {IAP_ASSERTION_HEADER: "x"},
            StubVerifier({"email": "a@b.c", "sub": "s", "iss": "https://evil.example"}),
        ),
    ],
)
async def test_iap_provider_rejects_bad_assertions(
    headers: dict[str, str], verifier: StubVerifier
) -> None:
    with pytest.raises(UnauthenticatedError):
        await IapIdentityProvider("aud", verifier=verifier).identify(headers)


def test_iap_provider_needs_an_audience() -> None:
    with pytest.raises(ValueError, match="audience"):
        IapIdentityProvider("")
