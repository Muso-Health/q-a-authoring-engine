from __future__ import annotations

import pytest

from config.auth import identity_provider_from_settings
from config.settings import Settings
from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from qa_authoring.infrastructure.auth.iap import IapIdentityProvider


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(f"QA_AUTHORING_{key}", value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_iap_is_selected_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = identity_provider_from_settings(_settings(monkeypatch, AUTH_IAP_AUDIENCE="aud"))
    assert isinstance(provider, IapIdentityProvider)


def test_iap_without_an_audience_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="audience"):
        identity_provider_from_settings(_settings(monkeypatch))


def test_dev_is_selected_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = identity_provider_from_settings(_settings(monkeypatch, AUTH_PROVIDER="dev"))
    assert isinstance(provider, DevIdentityProvider)
