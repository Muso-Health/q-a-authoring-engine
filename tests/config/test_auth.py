from __future__ import annotations

import pytest

from config.auth import identity_provider_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from qa_authoring.infrastructure.auth.entra import EntraIdentityProvider


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_entra_is_selected_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = identity_provider_from_settings(
        _settings(monkeypatch, AUTH_ENTRA_AUDIENCE="api://qa", AUTH_ENTRA_TENANT="tenant-id")
    )
    assert isinstance(provider, EntraIdentityProvider)


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({"AUTH_ENTRA_TENANT": "tenant-id"}, "audience"),
        ({"AUTH_ENTRA_AUDIENCE": "api://qa"}, "tenant"),
        ({}, "audience"),
    ],
)
def test_entra_without_its_settings_refuses_to_start(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], missing: str
) -> None:
    with pytest.raises(ValueError, match=missing):
        identity_provider_from_settings(_settings(monkeypatch, **env))


def test_dev_is_selected_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = identity_provider_from_settings(_settings(monkeypatch, AUTH_PROVIDER="dev"))
    assert isinstance(provider, DevIdentityProvider)
